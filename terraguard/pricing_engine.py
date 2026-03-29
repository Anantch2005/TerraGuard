import boto3
import json

class AWSPricing:
    def __init__(self):
        self.client = boto3.client("pricing", region_name="us-east-1")

        self.region_map = {
            "us-east-1": "US East (N. Virginia)",
            "ap-south-1": "Asia Pacific (Mumbai)"
        }

        self.cache = {}

    def get_price(self, service_code, filters):
        key = str((service_code, tuple([tuple(f.items()) for f in filters])))

        if key in self.cache:
            return self.cache[key]

        try:
            response = self.client.get_products(
                ServiceCode=service_code,
                Filters=filters,
                MaxResults=1
            )

            if not response["PriceList"]:
                return None

            price_item = json.loads(response["PriceList"][0])

            terms = price_item["terms"]["OnDemand"]
            term_id = list(terms.keys())[0]

            price_dimensions = terms[term_id]["priceDimensions"]
            price_id = list(price_dimensions.keys())[0]

            price = float(price_dimensions[price_id]["pricePerUnit"]["USD"])

            self.cache[key] = price
            return price

        except Exception as e:
            print("Pricing error:", e)
            return None