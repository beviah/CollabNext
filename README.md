# CollabNext

This project is hackaton challenge / contribution to *Building the Prototype Open Knowledge Network (Proto-OKN)*, a NSF funded project. 

https://new.nsf.gov/funding/opportunities/building-prototype-open-knowledge-network-proto

The goal is to build a Knowledge Graph based recommendation system for researchers, to help them find collaborators given specified constrains, i.e. topics or universities. 

The first script is ETL code for fetching data from [OpenAlex API](https://openalex.org/), filtering it, and inserting institutions, topics, authors, and works into Neo4j graph db. Initial prototype dataset is limited to [HBCU](https://en.wikipedia.org/wiki/List_of_historically_black_colleges_and_universities) institutions, around 100 of them.. goal is to discover researchers less visible with common academic tools (i.e. giving preference to high citations counts and reinforcing Mathew effect / preferential attachment)


Current ETL starts with a 
 - list of institutions (universities)
 - ... or any endpoint from the API except 📄Works (as it further expands by works API and specified filter):
 - 👩Authors, 📚Sources, 🏫Institutions, 💡Topics, 🏢Publishers, 💰Funders, 🌎Geo, 💡Concepts

It then fetches whatever is in the **lkeep** set, while looking through **keep** properties... so you can modify those. Script is generic, it filters those massive jsons based on your property list. OpenAlex has 3 billion triplets, so it is not practical to filter those for prototyping purposes and with limited resources. One could start from a single uni/author/work, and start expanding graph connections, until satisfying results/recommendations are found.. but then the graph can explode rapidly depending on connectivity of authors/institutions.. so a smarter real time filtering by i.e. topics would be practical!


## Examples

 - Q: Which author from Eastern Oregon University worked on protein supplementation?
   - A: Bruno I Cappellozza, D. W. Bohnert, M. M. Reis, Megan L Van Emon, C. S. Schauer, S. J. Falck, Reinaldo F Cooke from Eastern Oregon University worked on protein supplementation.

 - Q: Give me institutions which explore mechanical engineering.
   - A: University of Tennessee at Chattanooga, Chattanooga State Community College, Lawson State Community College explore mechanical engineering.

 - Q: Give me institution with most authors of works.
   - A: Tuskegee University has the most authors of works with a total of 3557.

 - Q: Give me institution with most authors of works on biology.
   - A: Cornell University has the most authors of works on biology.

 - Q: Give me institution with most authors of works on biology which have centrality less than 10
   - A: Delaware State University has the most authors of works on biology with centrality less than 10
  
 - Q: Give me institution with most different communities of authors of works on social justice
   - A: Miles College has 1 community of authors of works on social justice.
