import json, os, requests, urllib.parse, re, pandas as pd, hashlib, pickle, pysbd, random, sys, uuid, numpy as np
from envs import * # set os.environ(s) here
from pathlib import Path
#from py2neo import Graph, Node, Relationship, NodeMatcher
#from google.colab import userdata
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.runnables import (
    ConfigurableField,
    RunnableBranch,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)
#from langchain_mistralai.chat_models import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.prompt import PromptTemplate
#from langchain.prompts.prompt import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Tuple, List, Optional
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain.text_splitter import TokenTextSplitter
#from langchain_experimental.graph_transformers import LLMGraphTransformer
#from yfiles_jupyter_graphs import GraphWidget
from langchain_community.vectorstores import Neo4jVector
#from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.neo4j_vector import remove_lucene_chars
from langchain_community.embeddings import HuggingFaceEmbeddings
embedder = HuggingFaceEmbeddings(
    model_name = "sentence-transformers/allenai-specter"
)
#import mistralai
from langchain_community.llms import Ollama
llm = Ollama(model="llama2")
llm=ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo-0125")

#import ollama
#from ollama import Client
#client = Ollama.Client(host='http://localhost:11434')
from sentence_transformers import SentenceTransformer, util
#graph = Graph('neo4j+s://8e687b1d.databases.neo4j.io', user="neo4j", password=userdata.get('NEO4J_PASSWORD'))#plan to upload from local to this instance
#

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

    session.close()
    

#already done
#add_community_labels()


if False:#already done
    print('vectors')
    vector_index = Neo4jVector.from_existing_graph(
        embedding=embedder,#OpenAIEmbeddings(),
        search_type="hybrid",
        node_label="work",
        text_node_properties=["title_abstract"],
        embedding_node_property="embedding",
        index_name="vectors"
    )


if False: # no need for this.. 
    session = driver.session()
    session.run("""CALL gds.alpha.addNodeProperties('work', 'vectors', {'property':'embedding'})""")
    session.close()

existing_vector_index = Neo4jVector.from_existing_index(
    embedder,
    database="neo4j",
    index_name="vectors",
    text_node_property="title_abstract",
    #text_node_property="title_abstract",
)

print(existing_vector_index.similarity_search("Give me some random results and methods.", k=2)) # returns empty set, as if index is empty.. but its not. 

if False: # already done in neo browswer
    # This is a chortcut solution for the demo, search all text fields at once, hope classic IR algo returns the most relevant
    #  instead of using specific queries for question types like this approach:
    #   https://github.com/tomasonjo/blogs/blob/master/llm/langchain_neo4j_tips.ipynb
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
    #CREATE FULLTEXT INDEX combinedIndex FOR (n:institution|author|work) ON EACH [n.display_name, n.title_abstract]
    #TODO: include more fields.. generalize based on ETL step lkeep set
    pass


    """ just testing in neo4j browswer basic queries. vector does not work... super frustrating. returns empty set.

    CALL db.index.fulltext.queryNodes('combinedIndex', 'results~2 AND method~2', {:2})
    YIELD node, score
    CALL {
      MATCH (node)-[r:INTERACTS]->(a:author)
      RETURN node.display_name + ' - ' + type(r) + ' -> ' + a.display_name AS output
    }
    RETURN output  50

    CALL db.index.vector.queryNodes('vectors', 3, [-0.6348793506622314, -0.0467035211622715, 0.07295873761177063, -0.2797473669052124, -0.056764259934425354, -0.6571632623672485, 1.276459813117981, -0.253403902053833, -0.1586270034313202, 0.6201665997505188, 0.4614538848400116, -0.7678588032722473, -0.8322886228561401, 0.7193433046340942, -0.21023891866207123, -0.26769834756851196, -0.4923192262649536, 0.4744173288345337, -0.21357481181621552, -0.35124096274375916, -0.22991399466991425, -0.5174476504325867, 0.12579397857189178, 1.4872692823410034, -0.9061678051948547, 0.06215565651655197, 1.2752561569213867, -0.1842489242553711, 0.014827482402324677, -0.14787885546684265, -0.15064653754234314, 0.5394575595855713, 0.08208170533180237, 0.5381274819374084, -0.5577521920204163, 0.30008503794670105, -0.6114006638526917, 0.02666543237864971, -0.5475680828094482, -0.3289744257926941, -0.21835313737392426, 0.24522629380226135, 0.6780235767364502, 0.3158048689365387, -1.2246633768081665, 0.1016683354973793, -0.3210752308368683, 0.5413235425949097, -0.546904444694519, -0.5067617893218994, 0.40361452102661133, 0.7859048247337341, -0.22886019945144653, -0.42433616518974304, 0.25394025444984436, 0.8452873229980469, -0.47434288263320923, -0.6652635931968689, -0.4991966784000397, 0.28325384855270386, 0.03733674809336662, -0.5548316836357117, 0.5072582960128784, 0.18342456221580505, 0.513670027256012, -0.3311164379119873, -0.19470146298408508, -0.8481845259666443, -0.17806623876094818, 0.8752198815345764, 0.4493703842163086, -0.8345960378646851, 0.900273323059082, -0.5888994336128235, 0.2733975946903229, -0.1263795644044876, -0.27672088146209717, -0.25649720430374146, -0.35826754570007324, 0.13788720965385437, 0.060479067265987396, 0.1910112053155899, 1.4976236820220947, -0.23262128233909607, 0.07725221663713455, -0.2639191448688507, 0.4052872359752655, -0.5718083381652832, 0.427836537361145, -0.8456760048866272, 0.46803581714630127, 0.05735506862401962, 1.2553969621658325, 1.0734169483184814, -0.5302634835243225, 0.2786981165409088, -0.2339514046907425, -0.17183241248130798, 0.02946644276380539, 0.532774031162262, -0.596653938293457, -1.3440437316894531, 0.3116442859172821, -0.410144180059433, 0.3149326741695404, -0.5977506637573242, 0.6908608675003052, -0.0335674062371254, 0.7632079124450684, -0.0768466368317604, 0.010330099612474442, 0.8864114880561829, 0.4791088402271271, 0.9408241510391235, -0.8828715085983276, 1.0593937635421753, -0.7019464373588562, -1.0808537006378174, 0.23601330816745758, 0.9268381595611572, 1.0776145458221436, -1.4153149127960205, -0.2304506003856659, 0.12283530831336975, 0.980778694152832, -0.19216829538345337, 0.04357747361063957, -0.7436545491218567, -1.3365169763565063, -0.337509423494339, 0.5491020679473877, -0.21192915737628937, -0.10181529819965363, 0.326629102230072, 2.4573521614074707, -0.033188752830028534, 1.0527695417404175, -0.04458840936422348, -0.9485241770744324, -0.9163734912872314, -0.4538780152797699, -0.9430655241012573, -0.15194207429885864, -0.6202466487884521, 0.15990391373634338, 0.3618375360965729, 0.25299906730651855, 0.0880112275481224, -0.16499142348766327, 0.23738503456115723, 0.7039928436279297, -0.29256293177604675, -0.7093693017959595, -0.3881542682647705, -0.04570555314421654, 0.03999239206314087, 0.04561362788081169, -0.3584592938423157, -0.7318171858787537, 0.06014043837785721, -0.04089822620153427, -0.026196300983428955, -0.3049565553665161, 0.05668479576706886, 0.20901000499725342, 0.05684542655944824, 1.2335697412490845, 0.4650091230869293, -1.052734613418579, -0.20408950746059418, 0.013869324699044228, 0.934063732624054, 0.34989312291145325, 0.005893354304134846, 0.11479894071817398, -0.12668246030807495, -0.43884706497192383, 0.48882946372032166, 0.5843701958656311, 0.49021661281585693, -0.05310085415840149, 0.040614284574985504, -0.0904979333281517, -0.016371121630072594, 0.7989018559455872, 0.5008067488670349, -1.0293476581573486, 0.9106194972991943, -1.7347630262374878, -0.2550651431083679, 0.7104546427726746, 0.73358553647995, 1.0394959449768066, 0.6201112270355225, -0.7325434684753418, 0.18510060012340546, 0.275616854429245, -1.413013219833374, -0.814308762550354, 0.1372440755367279, -0.3318853974342346, -0.01564110815525055, -0.6408697366714478, 0.8812456130981445, 0.12983541190624237, 0.49851489067077637, -0.29052284359931946, -2.0361688137054443, 0.8142346143722534, 1.0978195667266846, -0.3269909620285034, -0.016362063586711884, -0.33436208963394165, 0.04149945080280304, 0.16611242294311523, -0.7739999890327454, -0.47560203075408936, 0.020399905741214752, -0.5138084292411804, -0.2099890410900116, -0.4823574423789978, 0.34026724100112915, 1.716687798500061, -0.11113936454057693, 0.5745216012001038, -0.7726103663444519, -1.1428626775741577, -0.07723243534564972, -1.1812257766723633, 0.5919350981712341, 0.3438095450401306, 0.15076200664043427, 1.04649019241333, -0.08732578158378601, -0.3008235692977905, 0.1419186294078827, 0.22913870215415955, 0.8555186986923218, -0.1337476223707199, -0.38300755620002747, 0.5285019278526306, 1.2713348865509033, -0.7174914479255676, 0.21070009469985962, 0.02960948646068573, -0.6513150334358215, -0.294636607170105, 0.1752716451883316, -0.30993586778640747, -0.5758666396141052, 1.1573026180267334, 0.21478822827339172, 0.07933224737644196, 0.125481516122818, 0.41170188784599304, -0.5486879348754883, 1.1442030668258667, -0.18631823360919952, -0.3997355103492737, 0.36305487155914307, -0.04118341952562332, 0.049153558909893036, -0.6901706457138062, -0.9369627833366394, 0.44287341833114624, 0.2228178232908249, -0.5787725448608398, -0.8067630529403687, 0.018598251044750214, -0.3889364004135132, 0.7562276124954224, 0.6938854455947876, -1.0186268091201782, 0.7783311605453491, 0.1356605887413025, 0.37835657596588135, 0.18249249458312988, 0.6832265853881836, -0.00020080432295799255, -0.04628594592213631, 0.37731021642684937, -0.533994734287262, 0.03259170055389404, -0.16883708536624908, 0.8976466655731201, -0.5330795645713806, -0.5363368988037109, 1.0594720840454102, -0.370963454246521, -0.48532330989837646, 0.44437021017074585, 0.46957194805145264, -0.8275779485702515, 0.5732235908508301, -0.24788452684879303, -0.837998628616333, 1.0655009746551514, 1.1516690254211426, -0.28634753823280334, 0.7652174830436707, -0.13764339685440063, -0.11211291700601578, 0.29101869463920593, 0.782267153263092, -1.0740721225738525, 0.21050678193569183, 1.4768248796463013, 0.4901537001132965, -0.6838651299476624, 0.33493727445602417, -0.7136678099632263, -0.49165013432502747, 0.2599707841873169, -1.4591712951660156, 0.5864232778549194, -0.017984861508011818, -0.5667174458503723, 0.0603967159986496, -1.3342292308807373, -0.45874977111816406, -0.7678294777870178, 0.37498316168785095, -0.1836954951286316, -0.5538461208343506, 0.4284456968307495, -0.7870855927467346, -0.3944380283355713, 0.014598757959902287, -1.3401908874511719, -0.2061029076576233, -0.3837170898914337, 1.130590558052063, -1.547651767730713, -0.12446492165327072, 0.5687364339828491, 0.09436000138521194, 0.12211427837610245, 0.8352123498916626, 1.5145998001098633, 0.9272274971008301, -0.5063099265098572, -0.20867694914340973, 0.0421324223279953, 0.015450112521648407, 0.6568446159362793, 0.3485546112060547, 0.37022989988327026, 0.4121696949005127, 0.1506357043981552, 0.5143485069274902, -0.8343640565872192, 0.10795867443084717, 0.3281508982181549, -0.6698734164237976, -0.474017858505249, -0.030833084136247635, 0.7787248492240906, 0.7321466207504272, 1.2006510496139526, -0.6828888654708862, 0.47316011786460876, -0.030230242758989334, 0.14815664291381836, 0.5053718686103821, 0.28848376870155334, -0.25211167335510254, 0.3578658998012543, 0.42331284284591675, -0.045627884566783905, 0.4632130563259125, -0.570530891418457, 0.02155737578868866, -0.22222644090652466, 1.0638083219528198, 0.2851906418800354, 1.1022441387176514, -0.0743069052696228, 0.7570388317108154, 0.8731598854064941, 0.178596630692482, 1.0307537317276, -0.3847813904285431, -0.7044195532798767, 0.3160931169986725, -1.168328881263733, -0.4194246232509613, 0.43075060844421387, -0.30617019534111023, 1.2490941286087036, 0.17428593337535858, 0.09795468300580978, -0.23843401670455933, -0.6372208595275879, -1.024231195449829, -0.03236225247383118, -0.6027761697769165, 0.3231678307056427, 0.7652243971824646, -0.11248362064361572, -0.2709812521934509, 1.077345371246338, -0.09260459989309311, -0.28660401701927185, 0.6615701913833618, 0.6305519342422485, -0.7060092687606812, -0.2702614665031433, 1.0061988830566406, -0.731824517250061, 0.9576041102409363, -0.4330670237541199, -0.3401934504508972, -0.6694980263710022, 0.0012122513726353645, -0.13909484446048737, 1.4217888116836548, -0.9533599615097046, 0.01672513410449028, -0.6370148658752441, -0.07065897434949875, 0.5576379299163818, 1.0413206815719604, -0.35782819986343384, 0.25241991877555847, 0.5927183628082275, 0.8289709687232971, 0.423448383808136, 0.5950936079025269, -1.3688441514968872, 0.12823718786239624, 1.312524676322937, -0.046843405812978745, -0.3473154902458191, -0.36531615257263184, -0.3146205246448517, -0.20468178391456604, 0.32450753450393677, 1.1515284776687622, -1.0921381711959839, -0.06693233549594879, -0.6495533585548401, 0.49779489636421204, 0.6497821807861328, -0.6257855892181396, -1.0369524955749512, 1.1320970058441162, -1.0315624475479126, -0.38964423537254333, -0.7271552085876465, -0.6243942975997925, 1.7653316259384155, -0.4815446138381958, 0.18511874973773956, -0.5577511787414551, -11.664381980895996, -0.07916580140590668, -0.6341153979301453, 0.18506117165088654, 0.2550693154335022, 0.4733826220035553, -0.03992693871259689, -0.8132628202438354, 1.7730354070663452, -0.39535436034202576, -0.21369515359401703, 1.438567042350769, 0.923079788684845, -0.5238217115402222, -1.6724516153335571, -1.5701160430908203, 0.7861419320106506, 0.41237080097198486, -0.507683277130127, 0.31448718905448914, 0.4238130450248718, -1.6941916942596436, 1.0690408945083618, -0.7103102207183838, -0.22677499055862427, -1.7025067806243896, -0.09690196067094803, -0.6581781506538391, -0.14362327754497528, 0.02497933804988861, 0.6217239499092102, 0.05833347886800766, -0.0016550272703170776, -0.8942786455154419, -0.014533743262290955, -0.10550311207771301, -0.803202748298645, -0.6429439783096313, 1.144945740699768, 0.42593687772750854, -0.6523423194885254, -0.11120905727148056, 0.6006414890289307, 0.1845751255750656, -0.009509922936558723, -0.3174254596233368, -0.6107174158096313, -0.048271626234054565, -0.36283767223358154, -0.6547232866287231, -0.10620643198490143, 0.2668039798736572, 0.13842809200286865, -0.8364532589912415, 0.34628772735595703, 0.496198445558548, -1.2828161716461182, -0.7583220601081848, -2.7231242656707764, -1.3184700012207031, 0.48789894580841064, -0.7541431188583374, -0.9072158932685852, 1.0759446620941162, -0.2553132176399231, -1.0776547193527222, 0.13989782333374023, 0.08110079169273376, -0.5413928031921387, 0.47252345085144043, -0.07009714096784592, 1.053633451461792, 0.8843862414360046, -0.43777501583099365, 0.4841814637184143, 0.03277042880654335, -0.4433993697166443, 0.21041744947433472, 0.3229316473007202, -1.4486804008483887, -0.5594258904457092, 0.5614623427391052, -0.0965392142534256, 0.19873517751693726, -0.037149880081415176, 1.2049951553344727, 0.2197674810886383, -0.7050859332084656, 1.5365359783172607, -0.6717818975448608, 0.04399489238858223, 0.6460148692131042, -0.6254878640174866, 0.21186745166778564, -1.1613940000534058, 0.5108094215393066, 0.7056736946105957, 0.6560871601104736, 0.6066327095031738, -0.12176846712827682, 0.29973530769348145, 0.5439808964729309, 0.20990057289600372, -0.6539590358734131, 0.6321412920951843, -0.4048278331756592, 0.41263294219970703, 0.7425746917724609, -0.3237318694591522, 0.17811883985996246, -0.5573937296867371, 0.11419056355953217, 0.077155202627182, -0.059475377202034, -0.928428053855896, 0.4813913404941559, 0.3703557252883911, -0.6529513001441956, -0.02271137945353985, 0.8801653385162354, 0.5465388298034668, -0.5556849837303162, 0.4751428961753845, 0.33478856086730957, 0.44659164547920227, -0.4936576187610626, 0.15637338161468506, 0.2975102663040161, -0.7476577162742615, -1.3030860424041748, 0.3746359348297119, -0.002275858074426651, 0.052088432013988495, 0.5194044709205627, -0.4526274800300598, -0.1425924003124237, 0.3853585124015808, 0.22521594166755676, -0.865623950958252, 0.34743592143058777, -0.773256778717041, -0.49925991892814636, -1.095240831375122, 1.0903871059417725, -0.8732916712760925, 0.5586565732955933, -0.8432912826538086, 0.6521042585372925, 0.1539921760559082, -0.6879937052726746, -0.695141077041626, -0.27167031168937683, 0.25466030836105347, 0.3261803984642029, -0.24439658224582672, -0.8729556202888489, 0.14354199171066284, 0.3391326367855072, 0.120599165558815, -0.49405965209007263, 1.504969596862793, 0.5611066818237305, -1.8365256786346436, 0.9256247878074646, 0.7675654888153076, -0.18009817600250244, -1.3375039100646973, -0.24894441664218903, 0.3016555905342102, 1.1495739221572876, -0.3998432755470276, -0.5254666209220886, -0.5240045785903931, 0.6217581629753113, 0.9898762106895447, -0.366786926984787, 0.7469412088394165, -0.05627104640007019, -1.185450553894043, -0.2185715287923813, 0.0722259059548378, 0.479758083820343, 0.39019060134887695, -0.6760837435722351, -0.7863970994949341, 0.05830533057451248, 0.04171523079276085, 1.0472779273986816, -0.3792589604854584, 0.7798161506652832, -1.4845280647277832, -0.7213700413703918, 0.5656857490539551, 1.7961337566375732, 1.0902289152145386, -0.0264817513525486, 1.6333370208740234, 0.4511391520500183, -1.583517074584961, -0.0657297819852829, -0.056159477680921555, 1.3044400215148926, 1.1880605220794678, 0.4746077060699463, -0.687620222568512, -0.14694690704345703, -1.5623173713684082, -1.6019937992095947, 0.04770543798804283, 1.1946187019348145, -0.8500216603279114, -0.5062256455421448, 0.8365123271942139, -0.3078077435493469, 0.27434241771698, -0.7907867431640625, -0.24839216470718384, -0.17473068833351135, 0.3473251163959503, -1.496548056602478, 0.7454420328140259, 0.6292866468429565, 0.007514156401157379, -0.08681261539459229, -0.40420883893966675, 0.6961951851844788, 0.16653987765312195, 0.6999079585075378, 1.1245158910751343, 1.4860730171203613, 0.06817672401666641, 0.34338587522506714, 0.5788867473602295, -0.24638989567756653, -0.4440620243549347, -0.6153008341789246, -0.5321959853172302, 0.5569172501564026, -0.6184276938438416, 0.04129675775766373, -0.48843175172805786, 1.061687707901001, 0.6039625406265259, 0.6842165589332581, -0.9779258966445923, -1.4603310823440552, -0.04185095429420471, -0.5604478120803833, 1.1697793006896973, 0.7982373833656311, 0.16883988678455353, 0.5029619336128235, 0.2412766069173813, -0.5899888873100281, -0.5199805498123169, -0.6820669174194336, 0.6681636571884155, -0.34572702646255493, 0.42216384410858154, 0.5508793592453003, 0.7944130301475525, -0.09100291132926941, 0.0978156328201294, 0.35181546211242676, -0.9869138598442078, 0.35456138849258423, -0.9998064041137695, 0.7091816067695618, 0.05140209197998047, -0.5830283164978027, -1.1934493780136108, 1.1340625286102295, 0.6657877564430237, -0.8452358245849609, 0.10636156797409058, 1.2221713066101074, 0.6753160953521729, -0.9062005877494812, -0.36366280913352966, 0.9835688471794128, -0.42446163296699524, -0.18631766736507416, -0.508898138999939, -0.36476147174835205, 1.0114047527313232, 0.47300985455513, -0.22146953642368317, 0.5282601118087769, 0.45625442266464233, 0.3068901300430298, 1.3593785762786865, -0.7229044437408447, -1.4158252477645874, 0.06802515685558319, 0.6387184262275696, -0.2846055328845978, 0.42121776938438416, -0.9706290364265442, 0.03927040100097656, 0.10520978271961212, 0.0016254670917987823, -0.5025197267532349, 0.1272680014371872, 0.7648335695266724, 1.3570905923843384, -0.9991327524185181, 1.6347118616104126, 0.46824291348457336, -0.509536862373352, -0.7294973731040955, -0.063788503408432, 0.27869367599487305, -0.2920111417770386, 0.2295261025428772]) yield node
    """

CYPHER_GENERATION_TEMPLATE = """Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.
Schema:
{schema}
Cypher examples:
#Query: Which author from the Tuskegee University worked on biochemical parameters ?
MATCH (i:institution)-[]-(w:work)-[]-(a:author)
WHERE toLower(w.title_abstract) CONTAINS "biochemical parameters"
AND toLower(i.display_name) CONTAINS "tuskegee university"
RETURN DISTINCT a.id, a.display_name, w.title, i.display_name
LIMIT 3
#Query: give me institutions which explore mechanical engineering, by seeing which associated works have associated concepts.
MATCH (i:institution)-[:INTERACTS]->(w:work)-[:INTERACTS]->(c:concepts|topics|keywords|x_concepts)
WHERE toLower(c.display_name) CONTAINS "mechanical engineering"
RETURN DISTINCT i.display_name, i.id, w.title, c.display_name
LIMIT 3
#Query: give me institutions which explore mechanical engineering.
MATCH (i:institution)-[:INTERACTS]->(w:work)-[:INTERACTS]->(c:concepts|topics|keywords|x_concepts)
WHERE toLower(c.display_name) CONTAINS "mechanical engineering" OR toLower(w.title) CONTAINS "mechanical engineering"
RETURN DISTINCT i.display_name, i.id, w.title, c.display_name
LIMIT 3

Note: Always treat (c:concepts|topics|keywords|x_concepts) nodes as one in the search
Note: For work nodes use 'title_abstract' property, for every other node type/label use 'display_name'!
Note: work is central node connected to institutions and authors.
Note: Do not include any explanations or apologies in your responses.
Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
Do not include any text except the generated Cypher statement.

The question is:
{question}"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
)


chain_language_example = GraphCypherQAChain.from_llm(
    ChatOpenAI(temperature=0), graph=graph, verbose=True,
    cypher_prompt=CYPHER_GENERATION_PROMPT
)

chain_language_example.invoke({'query':"""
Which author from Eastern Oregon University worked on protein supplementation?
"""})


