# CollabNext

This project is hackaton challenge / contribution to *Building the Prototype Open Knowledge Network (Proto-OKN)*, a NSF funded project. 

https://new.nsf.gov/funding/opportunities/building-prototype-open-knowledge-network-proto

The goal is to build a Knowledge Graph based recommendation system for researchers, to help them find collaborators given specified constrains, i.e. topics or universities. 

The first script is ETL code for fetching data from OpenAlex API, filtering it, and inserting institutions, topics, authors, and works into Neo4j graph db. Initial prototype dataset is limited to HBCU institutions, around 100 of them.. goal is to discover researchers less visible with common academic tools (i.e. giving preference to high citations counts)
