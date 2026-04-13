# Project Name

Automated API Trading Script

## Overview
The Project analyse the data for all available data items' skins related to Counter Strike 2
Using API GraphQL server with encoded API-keys headers
Creates targets for buying items as well as post sell offers for holding skins
It runs 24/7 on the remote server 

## Problem
For analysing such a huge data set, script require time for get all the requests from Marketplace's server.

## Solution
Using parallelism and sending multiple GET requests using aiohttp module 

## Features
- All Itermidiate results during filtering the items are stored in Excel Files allowing faster finding bugs in script
- All the logs of each script run during the day are saved daily
- Encoding API-keys with NaCl.cripto_sign for safe requests

## Screenshots
Intermidiate results of analysing data
<img width="885" height="691" alt="image" src="https://github.com/user-attachments/assets/fa1e961c-2776-42c2-bd6c-55224b37cc86" />


## Demo
Link to live demo / video

## Tech Stack

Backend:  Python/
Database: Pandas/NaCl/Excel/

## Roadmap
- [x] MVP complete
- [ ] Beta launch
- [ ] Mobile app

## Status
Active (optimising)

## License
All rights reserved.
Public showcase only.
