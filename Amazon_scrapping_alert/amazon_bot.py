#https://www.youtube.com/channel/UC8nlj-qLSsT6twtd5Gtry9A
import time
import datetime
import requests
from bs4 import BeautifulSoup
from selenium import webdriver

import pprint



class AmazonBot:

    def __init__(self, mongodb_client, server_smtp):
        self.amazon_header =  {
            'authority': 'www.amazon.fr',
            'cache-control': 'max-age=0',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'sec-gpc': '1',
            'sec-fetch-site': 'none',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-user': '?1',
            'sec-fetch-dest': 'document',
            'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.mongodb_client = mongodb_client
        self.server_smtp = server_smtp
        # Ajouter ici le chemin vers chromedriver
        self.driver = webdriver.Chrome(executable_path="/home/pierrelouis/Bureau/chromedriver/chromedriver")

    def get_product_title(self, soup):
        try:
            return soup.find('span', {'id': 'productTitle'}).get_text().strip()
        except:
            return None
    
    def get_product_rating(self, soup):
        try:
            div_avg_cust_reviews = soup.find('div', {'id': 'averageCustomerReviews'})
            rating = div_avg_cust_reviews.find('span', {'class': 'a-icon-alt'}).get_text().strip().split()[0]
            return float(rating.replace(',', '.'))
        except:
            return None

    def get_product_nb_reviewers(self, soup):
        try:
            nb_reviewers = soup.find('span', {'id': 'acrCustomerReviewText'}).get_text().strip()
            return int(''.join(nb_reviewers.split()[:-1]))
        except:
            return None

    def get_product_price(self, soup):
        price_block=soup.find('div',{'id':'corePrice_desktop'})
        price = price_block.find('span', {'class': 'a-offscreen'}).get_text().strip()
        print('price',price)
        print(float(price.split()[0].replace(',', '.')))
        print('-----')
        try:
            price_block=soup.find('div',{'id':'corePrice_desktop'})
            price = price_block.find('span', {'class': 'a-offscreen'}).get_text().strip()
            print('price',price)
            print(float(price.split()[0].replace(',', '.')))
            return(float(price.split()[0].replace(',', '.')))
        except:
            try:
                price = soup.find('span', {'class': 'a-size-medium a-color-price offer-price a-text-normal'}).get_text().strip()
                return float(price.split()[0].replace(',', '.'))
            except:
                return None

    def get_product_data(self, product_url):
        self.driver.get(product_url)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        #r = requests.get(product_url, headers=self.amazon_header)
        #soup = BeautifulSoup(r.content, 'html.parser')
        title = self.get_product_title(soup)
        rating = self.get_product_rating(soup)
        nb_reviewers = self.get_product_nb_reviewers(soup)
        price = self.get_product_price(soup)

        return {
            "url": product_url,
            "title": title,
            "rating": rating,
            "nb_reviewers": nb_reviewers,
            "price": price,
            "update_date": datetime.datetime.now()
        }
    
    def scrap_urls(self):
        while True:
            # Query MongoDB pour récupérer les liens à scraper
            product_urls = self.mongodb_client["amazon"]["product_urls"].find({
                "$or": [
                    {"updated_at": None},
                    # On ne scrape un document que 5 minutes après l'avoir déja fait
                    # Vous pouvez augmenter cette valeur biensur
                    # Il vaut mieux éviter de spam Amazon de requetes sinon il risque de bloquer votre ip
                    {"updated_at": {"$lte": datetime.datetime.now() - datetime.timedelta(minutes=5)}}
                ]
            })

            for product_url in product_urls:
                print("Url à scraper:", product_url["url"], "\n")
                data = self.get_product_data(product_url["url"])
                print(data)
                # Upsert
                self.mongodb_client["amazon"]["product_data"].update({"url": product_url['url']}, {"$set": data}, upsert=True)
                # Update
                self.mongodb_client["amazon"]["product_urls"].update({"url": product_url["url"]}, {"$set":{
                    'updated_at': datetime.datetime.now()
                }})

                # Dernier prix enregistrer pour un produit
                try: 
                    last_product_price = self.mongodb_client["amazon"]["product_prices"].find({"url": data['url']}).sort([('created_at', -1)]).next()
                except:
                    last_product_price = None
                
                # On insert directement si aucun prix n'existe pour le produit en question
                if last_product_price is None:
                    # Insert
                    self.mongodb_client["amazon"]["product_prices"].insert({
                        "url": product_url["url"],
                        "price": data["price"],
                        "created_at": datetime.datetime.now()
                    })
                # Si il existe un précédent prix au produit et que celui-ci est différent
                # du prix que l'on vient de récuperer
                elif last_product_price is not None and last_product_price['price'] != data['price']:
                    # Insert
                    self.mongodb_client["amazon"]["product_prices"].insert({
                        "url": product_url["url"],
                        "price": data["price"],
                        "created_at": datetime.datetime.now()
                    })

                    # On check le type
                    if (type(data["price"]) is int or type(data['price']) is float) and \
                        (type(last_product_price["price"]) is int or type(last_product_price["price"]) is float):

                        # On calcule la différence entre l'ancien et le nouveau prix
                        diff_price_percentage = (1 - data["price"] / last_product_price["price"]) * 100

                        # S'il y a une baisse du prix on envoie un email
                        if diff_price_percentage > 0:
                            message = """
                            Diminution du prix de %s%% pour le produit %s.
                            Précédent prix: %s.
                            Nouveau prix: %s.
                            """ % (
                                diff_price_percentage, 
                                product_url["url"], 
                                last_product_price["price"], 
                                data["price"]
                            )
                            # On encode ici le message car j'y ai ajouté un caractére spécial le %
                            message = message.encode("utf-8")
                            # Ajouter l'email d'envoi et de réception du message
                            self.server_smtp.sendmail("pl.danieau1@gmail.com", "pl.danieau1@gmail.com", message)
