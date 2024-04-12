!pip install py2neo
!pip install hyperdb-python


import json, os, requests, urllib.parse
from hyperdb import HyperDB
from py2neo import Graph, Node, Relationship, NodeMatcher
from google.colab import userdata

def urlencode(query):return urllib.parse.quote_plus(query)

def clean_data(data):
    """Remove keys not in the 'keep' list."""
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items() if k in keep}
    elif isinstance(data, list):
        return [clean_data(item) for item in data]
    else:
        return data

def remove_subs(data):
    ndata = {}
    for key, value in data.items():
        if isinstance(value, list):continue
        if isinstance(value, dict):continue
        ndata[key]=value
    return ndata

def process_json(label, data, parent_label=None, parent_data=None):
    """Recursively process JSON to create nodes and relationships."""
    only_data = None
    doit = False
    if isinstance(data, dict):
        if 'id' in data:
            only_data = remove_subs(data)
            #create_or_update_node(label, only_data) # this is now done during relation.. 
        for key, value in data.items():
            if key in ['authors', 'topics', 'works', 'institutions', 'keywords']:key=key[:-1] #remove plural s; those were intermediary keys
            if key.startswith('primary_'):key = key[8:]#merge primary with other topics
            nlabel = key if key in lkeep else label
            if isinstance(value, dict):
                process_json(nlabel, value, label, only_data or parent_data)
            elif isinstance(value, list):
                for item in value:
                    process_json(nlabel, {nlabel: item}, label, only_data or parent_data)
            else:
                doit = True
    elif isinstance(data, list):
        for item in data:
            process_json(label, {label: item}, label, parent_data or data)
    else:
        return
        
    #if doit and 'id' in data: # this is now done during relation.. 
    #    create_or_update_node(label, only_data)
        
    if parent_label and parent_label!=label and parent_label in lkeep and label in lkeep:
        if only_data and parent_data:
            add_relationships(parent_data, only_data, parent_label, label)
        elif data and parent_data:
            add_relationships(parent_data, data, parent_label, label)

def create_or_update_node(label, properties):
    if label in properties:
        properties = properties[label]
    if not label or 'id' not in properties:
        return
        
    node = Node(label, **properties)
    matcher = NodeMatcher(graph)
    existing_node = matcher.match(label, id=properties['id']).first()
    if existing_node is None:
        graph.create(node)
        
    return existing_node or node

def add_relationships(parent_data, child_data, parent_label, child_label):
    parent_node = create_or_update_node(parent_label, parent_data)
    child_node = create_or_update_node(child_label, child_data)
    if parent_node and child_node:
        graph.merge(Relationship(parent_node, child_label, child_node))

def bad_geo(item):return starting=='institutions' and item['geo']['region'] and item['geo']['region'] != uni2state.get(query, '')

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

# Connect to Neo4j
graph = Graph('neo4j+s://8e687b1d.databases.neo4j.io', user="neo4j", password=userdata.get('NEO4J_PASSWORD'))

purge = False
if purge:
    tx = graph.begin()
    tx.run('MATCH (n) DETACH DELETE n')
    graph.commit(tx)

tx = graph.begin()


# define intermediary keys that need to be looked at
keep = {'id', 'publication_year', 'display_name',
        'author', 'authors', 'authorship', 'authorships',
        'works', 'work', #'title',
        'institution', 'institutions',
        'topics', 'topic', 'primary_topic', 'keywords', 'keyword', 'concepts',
        'grants', 'funder',
        'type',
        'affiliation', 'affiliations',
        'related_works', 'referenced_works'
        }

#define final labels of interested to be inserted into the graph
lkeep = {'publication_year', 'author', 'work', 'institution', 'topic', 'funder', 'primary_topic', 'keyword', 'concepts', 'related_works', 'referenced_works'}


starting_with = 'topics'

uni2state = {}
inputs = []
if starting_with == 'institutions':
    with open('inputs.tsv', 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():continue
            hbcu, city, state = line.split('\t')
            hbcu = hbcu.strip()
            state = state.strip()
            inputs.append(hbcu)
            uni2state[hbcu] = state
else:
    inputs = ['artificial intelligence']


for query in inputs:
    url = 'https://api.openalex.org/{0}?search={1}'.format(starting_with, urlencode(query))
    mdata = requests.get(url, headers=headers).json()
    if len(mdata['results'])==0:continue
    item = mdata['results'][0] # only top valid institution result, otherwise graph explosion is insane!
    if bad_geo(itme):continue
    
    item = clean_data(item)
    process_json('institution', item)

    graph.commit(tx)
    tx = graph.begin()

    iid = item['id'].split('/')[-1]

    #   https://api.openalex.org/works?filter=topics.id:T12260
    kvs = {
        #https://api.openalex.org/works?filter=institutions.id:I4210103791&per-page=200&cursor=*
        'work': 'https://api.openalex.org/works?filter={0}.id:{1}&per-page=200&cursor={2}'
        ###https://api.openalex.org/authors?filter=affiliations.institution.id:I4210103791&per-page=200&cursor=*
        ##'author': 'https://api.openalex.org/authors?filter=affiliations.institution.id:{0}&per-page=200&cursor={1}' #this is actually fetched through works, so no need for separate api calls. 
    }
    for what, url_template in kvs.items():
        cursor = '*'
        while True:
            url = url_template.format(starting_with, iid, cursor)
            data = requests.get(url, headers=headers).json()
            try:
                cursor = data['meta']['next_cursor']
            except:
                if 'results' not in data:
                    break
            itm = data['results']
            for i in itm:
                # TODO: here introduce some selectivity based on keywords/current connectivity, as some topics have 30k works... maybe skip older articles with many citations, focus on more recent ones. 
                i = clean_data(i)
                process_json(what, i) if what=='work' else process_json(what, {what:i}) #not sure if i need this now; i did at one point, but some refactoring happened since.. 

        graph.commit(tx)
        tx = graph.begin()


graph.commit(tx)
