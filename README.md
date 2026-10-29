
# Automated API Trading Script

## Overview
- The Project analyse the data for all available data items' skins on Counter Strike 2 ( The market of total cap ~$5.85 billion [https://pricempire.com/app/trending] )  
- With an algorithm developed by our team, scripts sort out items that do not pass the criterias 
- Using database on MySQL base to store and manipulate the data through SQLite3 Python library 
- Using API GraphQL server with encoded API-keys headers for DMarket market platform    
- Creates targets for buying items as well as post sell offers for holding skins    
- Deployed on EC2 instance on AWS cloud server with storage access S3

## Problem
For analysing such a huge data set, script require time for get all the requests from Marketplace's server( Consequent requests required ~40 minutes to complete the script).

## Solution
Using parallelism and sending multiple GET requests using aiohttp module (Time was reduced to ~10 minutes)

## Features
- All Itermidiate results during filtering the items are stored in Excel Files allowing faster finding bugs in script
- Data is stored in SQLite Database which can be easily read by PostgreSQL or MySQL client/server.
- All the logs of each script run daily are stored and send via email to user for keep them on track of any issues
- Encoding API-keys with NaCl.cripto_sign for safe requests
- Usage of Cloud Computing for monitoring and resource effeciency

## Tech Stack

#### Backend:  Python / Bash 
#### Libraries: aiohttp / JSON / pandas  
#### Database: Pandas / PyNaCl / Excel / SQLite3
#### Cloud: AWS

## Roadmap
- [x] Develop fully functional script
- [x] Launch on cloud server
- [ ] Implement Neural Network for adjusting algorithm choices

## Status
🟢 Active

## License
All rights reserved.
Public showcase only.
