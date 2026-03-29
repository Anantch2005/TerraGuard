from terraguard.pricing_engine import AWSPricing

pricing = AWSPricing()


def get_resource_cost(resource):
    rtype = resource.get("type")
    config = resource.get("config", {})

    region = config.get("region", "us-east-1")
    location = pricing.region_map.get(region, "US East (N. Virginia)")

    try:

        # ---------------- EC2 ----------------
        if rtype == "aws_instance":
            instance = config.get("instance_type", "t3.micro")

            return pricing.get_price(
                "AmazonEC2",
                [
                    {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance},
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                    {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                    {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                    {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                ],
            )

        # ---------------- EBS ----------------
        elif rtype == "aws_ebs_volume":
            size = config.get("size", 50)

            price = pricing.get_price(
                "AmazonEC2",
                [
                    {"Type": "TERM_MATCH", "Field": "volumeType", "Value": "General Purpose"},
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                ],
            )

            return (size * price) / (30 * 24) if price else None

        # ---------------- S3 ----------------
        elif rtype == "aws_s3_bucket":
            storage = config.get("storage_gb", 50)

            price = pricing.get_price(
                "AmazonS3",
                [
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                    {"Type": "TERM_MATCH", "Field": "storageClass", "Value": "General Purpose"},
                ],
            )

            return (storage * price) / (30 * 24) if price else None

        # ---------------- RDS ----------------
        elif rtype == "aws_db_instance":
            instance = config.get("instance_class", "db.t3.micro")

            return pricing.get_price(
                "AmazonRDS",
                [
                    {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance},
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                    {"Type": "TERM_MATCH", "Field": "databaseEngine", "Value": "MySQL"},
                ],
            )

        # ---------------- Lambda ----------------
        elif rtype == "aws_lambda_function":
            # Approx cost per request (simplified)
            return 0.00001667

        # ---------------- DynamoDB ----------------
        elif rtype == "aws_dynamodb_table":
            price = pricing.get_price(
                "AmazonDynamoDB",
                [
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                ],
            )
            return price / (30 * 24) if price else None

        # ---------------- Load Balancer ----------------
        elif rtype == "aws_lb":
            return pricing.get_price(
                "AmazonEC2",
                [
                    {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Load Balancer"},
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                ],
            )

        # ---------------- NAT Gateway ----------------
        elif rtype == "aws_nat_gateway":
            return pricing.get_price(
                "AmazonVPC",
                [
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                ],
            )

        # ---------------- Elastic IP ----------------
        elif rtype == "aws_eip":
            return pricing.get_price(
                "AmazonEC2",
                [
                    {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "IP Address"},
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                ],
            )

        # ---------------- CloudFront ----------------
        elif rtype == "aws_cloudfront_distribution":
            return pricing.get_price(
                "AmazonCloudFront",
                [
                    {"Type": "TERM_MATCH", "Field": "location", "Value": "Global"},
                ],
            )

        # ---------------- EKS ----------------
        elif rtype == "aws_eks_cluster":
            return 0.10  # per hour approx control plane

        # ---------------- Auto Scaling ----------------
        elif rtype == "aws_autoscaling_group":
            return 0.0  # cost depends on instances

        # ---------------- FREE ----------------
        elif rtype in [
            "aws_vpc",
            "aws_subnet",
            "aws_security_group",
            "aws_internet_gateway",
            "aws_route_table",
            "aws_route_table_association",
            "aws_key_pair",
        ]:
            return 0.0

        return None

    except Exception:
        return None