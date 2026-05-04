
# Automated API Trading Script

## Overview
The Project analyse the data for all available data items' skins related to Counter Strike 2 ( The market of total cap ~$5.85 billion [https://pricempire.com/app/trending] )  /  
Using API GraphQL server with encoded API-keys headers for DMarket market platform  /  
Creates targets for buying items as well as post sell offers for holding skins  /  
It runs 24/7 on the remote server   

## Problem
For analysing such a huge data set, script require time for get all the requests from Marketplace's server( Consequent requests required ~40 minutes to complete the script).

## Solution
Using parallelism and sending multiple GET requests using aiohttp module (Time was reduced to ~10 minutes)

## Features
- All Itermidiate results during filtering the items are stored in Excel Files allowing faster finding bugs in script
- All the logs of each script run daily are stored and send via email to user for keep them on track of any issues
- Encoding API-keys with NaCl.cripto_sign for safe requests

## Screenshots
#Q1 2025 
Monthly Sales
<img width="664" height="598" alt="Screenshot 2026-05-04 210958" src="https://github.com/user-attachments/assets/80b8191b-0665-49ca-a31b-5f76de4c1430" />
Gains & Losses 
<img width="956" height="282" alt="Screenshot 2026-05-04 211221" src="https://github.com/user-attachments/assets/a17a95c8-299f-4e8c-8c54-2f0d9db64b70" />

## Demo
Link to live demo / video

## Tech Stack

Backend:  Python/Bash
Libraries: aiohttp / JSON / pandas / 
Database: Pandas/NaCl/Excel

## Roadmap
- [x] Develop fully functional script
- [x] Launch on remote server
- [ ] Implement Neural Network for improving algorithm choices

## Status
🟢 Active

## License
All rights reserved.
Public showcase only.
