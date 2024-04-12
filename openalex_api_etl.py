!pip install py2neo

from py2neo import Graph, Node, Relationship, NodeMatcher
import json, os
from google.colab import userdata
import requests
import urllib.parse

def urlencode(query):return urllib.parse.quote_plus(query)

def remove_empty_lines(text):
    lines = text.split('\n')
    toremove = set()
    new = []
    state = ''
    uni2state = {}
    for i, line in enumerate(lines):
      if line.strip() and i not in toremove:
        line = line.split(' - ')[0] # ignoring cities for now.. if ambiguity exists, they should be considered.
        new.append(line)
        uni2state[line] = state
      elif not line.strip():
        toremove.add(i+1)
        state = lines[i+1]
    return '\n'.join(new), uni2state

with open('hbcus.txt', 'r') as f:
    hbcus = f.read()

hbcus, uni2state = remove_empty_lines(hbcus)


# define intermediary keys that need to be looked at
keep = {'id', 'publication_year', 'author', 'authors', 'authorship', 'authorships', 'display_name', 'works', 'work', 'title', 'institution', 'institutions', 'topics', 'topic', 'grants', 'funder', 'type', 'affiliation', 'affiliations'}

#define final labels of interested to be inserted into the graph
lkeep = {'author', 'work', 'institution', 'topic', 'funder'}

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
    if prn:print('0', parent_label, label, parent_data, data)
    """     {'institution': {'id': 'https://openalex.org/I91045830', 'display_name': 'Texas A&M University', 'type': 'education', 'topics': [...]}}
                {'topics': {'id': 'https://openalex.org/T10093', 'display_name': 'Theoretical and Experimental Nuclear Structure'}}
    """
    only_data = None
    doit = False
    if isinstance(data, dict):
        if 'id' in data:
            only_data = remove_subs(data)
            create_or_update_node(label, only_data)
        for key, value in data.items():
            if key in ['authors', 'topics', 'works', 'institutions']:key=key[:-1] #remove plural s; those were intermediary keys
            nlabel = key if key in lkeep else label
            if isinstance(value, dict):
                process_json(nlabel, value, label, only_data or parent_data)
            elif isinstance(value, list):
                for item in value:
                    process_json(nlabel, {nlabel: item}, label, only_data or parent_data)
            else:
                doit = True
                if prn:print('1', parent_label, label, nlabel, value)
    elif isinstance(data, list):
        for item in data:
            process_json(label, {label: item}, label, parent_data or data)
    else:
        return
        #if prn:print(parent_label, label, data)
        #create_or_update_node(label, {label:data})

    if data and 'id' in data:
        if parent_data and 'id' in parent_data:
            if prn:print('2', parent_label, label, parent_data, data, only_data)

    if doit and 'id' in data:
        if prn:print('3', parent_label, label, only_data, parent_data)
        create_or_update_node(label, only_data)

    if prn:print('4', parent_label, label, parent_data, data)

    if parent_label and parent_label!=label and parent_label in lkeep and label in lkeep:
        if only_data and parent_data:
            add_relationships(parent_data, only_data, parent_label, label)
        elif data and parent_data:
            add_relationships(parent_data, data, parent_label, label)

def create_or_update_node(label, properties):
    if prn:print('5', properties)
    if label in properties:
        properties = properties[label]
    """Create or update a node based on label and properties, with a unique constraint on 'id'."""
    if not label or 'id' not in properties:
        return  # Skip if no label or no 'id' in properties

    node = Node(label, **properties)
    matcher = NodeMatcher(graph)
    existing_node = matcher.match(label, id=properties['id']).first()

    if existing_node is None:
        graph.create(node)

    return existing_node or node

def add_relationships(parent_data, child_data, parent_label, child_label):
    """Add relationships from parent to child nodes."""
    if prn:print('6', parent_data, child_data, parent_label, child_label)
    parent_node = create_or_update_node(parent_label, parent_data)
    child_node = create_or_update_node(child_label, child_data)
    
    # Check if both nodes were successfully created or found
    if parent_node and child_node:
        relationship = Relationship(parent_node, child_label, child_node)
        graph.merge(relationship)
        if prn:print('7', parent_node, child_node, parent_label, child_label)


headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

# Connect to Neo4j
graph = Graph('neo4j+s://8e687b1d.databases.neo4j.io', user="neo4j", password=userdata.get('NEO4J_PASSWORD'))

tx = graph.begin()
tx.run('MATCH (n) DETACH DELETE n')
graph.commit(tx)

testing = False
prn = False

tx = graph.begin()

for uni in hbcus:
    url = 'https://api.openalex.org/institutions?search='+urlencode(uni)
    mdata = requests.get(url, headers=headers).json()
    if prn:
        print('INSTITUTION', url)
        print(len(mdata['results']))
    for item in mdata['results']:
        if item['geo']['region'] and item['geo']['region'] != uni2state.get(uni, ''):
            continue
        #institutions.append(item)
        #print(item)
        item = clean_data(item)
        process_json('institution', item)

        graph.commit(tx)
        tx = graph.begin()

        iid = item['id'].split('/')[-1]

        kvs = {
            #https://api.openalex.org/works?filter=institutions.id:I4210103791&per-page=200&cursor=*
            'work': 'https://api.openalex.org/works?filter=institutions.id:{0}&per-page=200&cursor={1}',
            
            #https://api.openalex.org/authors?filter=affiliations.institution.id:I4210103791&per-page=200&cursor=*
            'author': 'https://api.openalex.org/authors?filter=affiliations.institution.id:{0}&per-page=200&cursor={1}'
        }
        for what, url_template in kvs.items():
            #url_template = 'https://api.openalex.org/works?filter=institutions.id:{0}&per-page=200&cursor={1}'
            #data['meta']['next_cursor']
            cursor = '*'
            while True:
                url = url_template.format(iid, cursor)
                if prn:print(what.upper(), url)
                data = requests.get(url, headers=headers).json()
                try:
                    cursor = data['meta']['next_cursor']
                except:
                    if 'results' not in data:
                        break
                itm = data['results']
                #works.extend(itm)
                for i in itm:
                    i = clean_data(i)
                    process_json(what, i) if what=='work' else process_json(what, {what:i}) #not sure if i need this now; i did at one point, but some refactoring happened since.. 
                if testing:break

            graph.commit(tx)
            tx = graph.begin()

        break #only top valid institution result

graph.commit(tx)
