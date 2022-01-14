# Amazon webscrapping alert

## 🎯 Project description 

My github repo presents a project used to scrap the Amazon website list of products. Differents features are scrapped (like the title, the price, the review...), then stored in a MongoDB database. And finally we send automatic emails when we detect a reduction in the price of a product to alert the customer.

## 🤖 Program explanation

- amazon_bot.py : python web scrapping program using selenium and beautifulsoup
- main.py : main program (connect to de MongoDB, launch the scrapping & send email alert)
- requirements.txt : list of all dependencies

## 👨‍💻 Technologies used 
- Python (Beautifulsoup, selenium, smtplib...)
- MongoDB (storage)

