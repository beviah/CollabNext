import os
from envs import * # set os.environ(s) here
from langchain_community.graphs import Neo4jGraph
from langchain_community.vectorstores import Neo4jVector
from langchain_community.embeddings import HuggingFaceEmbeddings
embedder = HuggingFaceEmbeddings(
    model_name = "sentence-transformers/allenai-specter"
)

graph = Neo4jGraph(
    url=os.environ["NEO4J_URI"], 
    username=os.environ["NEO4J_USERNAME"], 
    password=os.environ["NEO4J_PASSWORD"]
)

def add_community_labels():
    # create a neo4j session to run queries
    session = driver.session()


    # add centrality scores to be used for finding secluded authors
    cypher = """
        CALL gds.graph.project('author_works', ['author', 'work'], 'INTERACTS') YIELD
            graphName AS graph, nodeProjection, nodeCount AS nodes, relationshipProjection, relationshipCount AS rels
    """
    session.run(cypher).graph()

    cypher = """
        CALL gds.betweenness.stream('author_works')
            YIELD nodeId, score
            WITH nodeId, score
            MATCH (n)
            WHERE id(n) = nodeId
            SET n.centrality = score
            RETURN n.display_name AS item, n.centrality AS centrality
            ORDER BY n.centrality
    """
    session.run(cypher).graph()

    # add community labels to be used for diversification
    cypher = """
        CALL gds.graph.project.cypher(
            'lgraph',
            'MATCH (n) RETURN id(n) AS id',
            'MATCH (n)-[r]->(m) RETURN id(n) AS source, id(m) AS target, type(r) AS type, properties(r) AS properties'
        )
    """
    session.run(cypher).graph()

    cypher = """
        CALL gds.labelPropagation.write.estimate('lgraph', { writeProperty: 'community' })
        YIELD nodeCount, relationshipCount, bytesMin, bytesMax, requiredMemory
    """
    session.run(cypher).graph()

    cypher = """
        CALL gds.labelPropagation.write('lgraph', {
            writeProperty: 'community'
        })
        YIELD communityCount, ranIterations, didConverge
    """
    session.run(cypher).graph()

    # add fulltext index
    """
    label	property
    institution	display_name
    topic	display_name
    x_concepts	display_name
    author	display_name
    keyword	display_name
    concepts	display_name
    work	title_abstract
    """
    cypher = """
        CREATE FULLTEXT INDEX combinedIndex FOR (n:institution|author|work) ON EACH [n.display_name, n.title_abstract]
    """
    #TODO: include more fields.. generalize based on ETL step lkeep set
    session.run(cypher).graph()
    
    session.close()
    

#done after initial ETL
add_community_labels()


print('vectors')
vector_index = Neo4jVector.from_existing_graph(
    embedding=embedder,#OpenAIEmbeddings(),
    search_type="hybrid",
    node_label="work",
    text_node_properties=["title_abstract"],
    embedding_node_property="embedding",
    index_name="vectors"
)

