#!pip install py2neo
import json, os, requests, urllib.parse, re, pandas as pd, hashlib, pickle, pysbd, random, sys, uuid, numpy as np
from pathlib import Path
from bs4 import BeautifulSoup
#from hyperdb import HyperDB
from py2neo import Graph, Node, Relationship, NodeMatcher
#from langchain_community.graphs import Neo4jGraph
#from google.colab import userdata

def get_sents(text):
    seg = pysbd.Segmenter(language=lid.predict(text)[:2], clean=False)
    return seg.segment(text)

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
            # FIXME: another hardcoded line, should reflect (l)keep changes.. 
            if key in ['authors', 'topics', 'works', 'institutions', 'keywords']:
                key=key[:-1] #remove plural s; those were intermediary keys
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

try:
    with open('categorical.pickle', 'rb') as f:
        categorical = pickle.load(f)
        icategorical = {v:k for k,v in categorical.items()}
        cmax = max(categorical.values())    
except:
    categorical = {}
    icategorical = {}
    cmax = 0

# these are actually not used.. thought I would need them at some point for some Neo4J procedures
def add_categorical(item):
    global cmax
    for key in list(item.keys()):
        if key+'_id' not in item:
            if item[key] in categorical:
                kid = categorical[item[key]]
            else:
                categorical[item[key]] = cmax
                icategorical[cmax] = item[key]
                kid = cmax
                cmax += 1
            item[key+'_id'] = kid
    return item            

local = not True
def local_json_writer(item):
    filename = 'data.jsonl'
    item = add_categorical(item)
    with open(filename, 'a', encoding='utf-8') as file:
        file.write(json.dumps(item) + '\n')

def generate_id_for_json_object(json_data):
    serialized_json = json.dumps(json_data, sort_keys=True)
    hash_object = hashlib.sha256(serialized_json.encode('utf-8'))
    unique_id = hash_object.hexdigest()
    return unique_id

def create_or_update_node(label, properties):
    if label in properties:
        properties = properties[label]
    if not label or 'id' not in properties:
        return

    properties['label']=label
    if not local:
        node = Node(label, **properties)
        matcher = NodeMatcher(graph)
        existing_node = matcher.match(label, id=properties['id']).first()
        if existing_node is None:
            graph.create(node)    
        return existing_node or node
    else:
        local_json_writer(properties)
        return generate_id_for_json_object(propreties)

global_cnt = 0
def add_relationships(parent_data, child_data, parent_label, child_label):
    global global_cnt
    parent_node = create_or_update_node(parent_label, parent_data)
    child_node = create_or_update_node(child_label, child_data)
    if parent_node and child_node:
        if not local:
            graph.merge(Relationship(parent_node, child_label, child_node))
            # https://neo4j.com/docs/graph-data-science/current/management-ops/graph-update/to-undirected/  # doing this in real time
            #   this simplifies later CYPHER generation by LLMs and reduces chance of error, while also reducing richness of expression..
            #      i.e. 'affiliated' becomes 'INTERACTS', but there is still such relation in schema, so not much harm done, LLM learns from schema. 
            graph.merge(Relationship(parent_node, 'INTERACTS', child_node))
            graph.merge(Relationship(child_node, 'INTERACTS', parent_node))
        else:
            local_json_writer({'parent_node':parent_node, 'child_node':child_node, 'relation':child_label})
        global_cnt += 1
        #print(global_cnt)

def bad_geo(item):return starting_with=='institutions' and item['geo']['region'] and item['geo']['region'] != uni2state.get(query, '')

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

# Connect to Neo4j
#graph = Graph('neo4j+s://8e687b1d.databases.neo4j.io', user="neo4j", password=userdata.get('NEO4J_PASSWORD'))
graph = Graph('bolt://localhost:7687', user="neo4j", password=os.environ["NEO4J_PASSWORD"])


purge = False
if purge:
    tx = graph.begin()
    tx.run('MATCH (n) DETACH DELETE n')
    graph.commit(tx)

tx = graph.begin()


# define intermediary keys that need to be looked at
keep = {'id', 'publication_year', 'display_name',
        'author', 'authors', 'authorship', 'authorships',
        'works', 'work', 'title',
        'institution', 'institutions',
        'topics', 'topic', 'primary_topic', 'keywords', 'keyword', 'concepts', 'x_concepts',
        'grants', 'funder',
        'type',
        'affiliation', 'affiliations',
        'related_works', 'referenced_works',
        'title_abstract' # reconstructed 
        }
keepdn = {k+'display_name' for k in keep}

#define final labels of interested to be inserted into the graph
lkeep = {
    # Top level nodes: Authors, Sources, Institutions, Topics, Publishers, Funders, Geo, Concepts: put them here and above if you want them in results!! 
    # Here you decide which labels to keep (final node is usually singular vs intermediary step also plural - needs to be looked up in API docs/json examples): 
    'publication_year', 'author', 'work', 'title', 'institution', 'funder', 'topic', 'primary_topic', 'keyword', 'concepts', 'x_concepts', 'related_works', 'referenced_works', 'title_abstract'}
lkeepdn = {k+'display_name' for k in lkeep}


def fetch_html(url):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors
        return response.text
    except requests.RequestException as e:
        return None

def cleanhtml(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def find_abstract(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    pattern = re.compile(r'<([^>]+)>\s*abstract.{0,2}<\/\1>.*?<([^>]+)>(.*?)<\/\2>', re.IGNORECASE | re.DOTALL)
    matches = pattern.findall(html_content)
    for match in matches:
        if len(match)==4:
            x = cleanhtml(match[-1].strip()).strip()
            if len(x) > 100:
                return ' '.join(x.split())
    return ''

def revert_index(abstract_inverted_index):
    if abstract_inverted_index is None:return ''
    words = []
    for word, indices in abstract_inverted_index.items():
        for ind in indices:
            words.append((ind, word))
    words = sorted(words)
    return ' '.join([word for _, word in words])
    
def parse_abstract(doi, i):
    if 'abstract_inverted_index' in i:
        return revert_index(i['abstract_inverted_index'])
    html = fetch_html(doi)
    return find_abstract(html) if html else ''



inputs = ['artificial intelligence']
inputs = []

starting_with = 'topics' if inputs else 'institutions' # make all these generic to handle diverse datasets.. 

years = list(range(2019,2025)) # only last ~5 years


# TODO: for this demo stopped at 20th institutions due to neo4j aura free cloud limits... ~400k relations and 200k nodes. should run full 100... 
done = 20 # primitive continuation.. should store last seen url

uni2state = {}
if starting_with == 'institutions': # should read node type from column name in CSV file
    with open('inputs.tsv', 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i<=0+done:continue #load this as csv file
            if not line.strip():continue
            hbcu, city, state = line.split('\t')
            hbcu = hbcu.strip()
            state = state.strip()
            inputs.append(hbcu)
            uni2state[hbcu] = state    


top_embeddings = []

#if starting_with == 'topics':
#    top_embeddings = model.encode(inputs, show_progress_bar=False, convert_to_numpy=True)

def valsonly(ikey):
    return list(valsonly(v) for k,v in ikey.items() if 'display_name' in k) if type(ikey)==dict else [valsonly(v) for v in ikey] if type(ikey)==list else ikey or ['']

for query in inputs:
    url = 'https://api.openalex.org/{0}?search={1}'.format(starting_with, urlencode(query))
    print(url)
    mdata = requests.get(url, headers=headers).json()
    if len(mdata['results'])==0:continue
    item = mdata['results'][0] # only top valid institution result, otherwise graph explosion is insane!
    if bad_geo(item):continue
    
    item = clean_data(item)
    process_json(starting_with[:-1], item)

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
            print(url)
            data = requests.get(url, headers=headers).json()
            try:
                cursor = data['meta']['next_cursor']
            except:
                if 'results' not in data:
                    break
            itm = data['results']
            print(len(itm))
            for i in itm:
                # TODO: here introduce some selectivity based on keywords/current connectivity, as some topics have 30k works... maybe skip older articles with many citations, focus on more recent ones. 
                if 'publication_year' in i and i['publication_year'] not in years:
                    continue
                
                if 'doi' in i:
                    doi = i['doi']
                    title = i['title']
                    abstract = title or '' +'. '+parse_abstract(doi, i)
                    
                i = clean_data(i)
                if abstract:
                    i['title_abstract'] = abstract

                all_topics = []
                for key in ['topic', 'primary_topic', 'keyword', 'concepts', 'x_concepts']:#, 'related_works', 'referenced_works']:
                    if key in i:
                        all_topics = all_topics+valsonly(i[key])
                        #print(all_topics)
                all_topics = list(set([item for sl in all_topics for item in sl]))
                if '' in all_topics:all_topics.remove('')

                # this is for real time filtering, but not really needed, as abstracts are now recreated from indexes, and json is already accessed... use vector store instead
                # embs + communities retrieves most relevant and distinct.
                # if i apply sims during graph building, only strong connections will remain, which should give more relevance during retrieval, but works only for the given query!!! very inneficient
                #embeddings = model.encode(get_sents(abstract)+all_topics, show_progress_bar=False, convert_to_numpy=True)
                #similarities = util.pytorch_cos_sim(top_embeddings, embeddings)
                #if max(similarities) > 0.9:
                #    pass # boost it

                process_json(what, i) if what=='work' else process_json(what, {what:i}) #not sure if i need this now; i did at one point, but some refactoring happened since.. 

            with open('categorical.pickle', 'wb') as f:
                pickle.dump(categorical, f, pickle.HIGHEST_PROTOCOL)

        graph.commit(tx)
        tx = graph.begin()
        if global_cnt > 10000:
            break


graph.commit(tx)
