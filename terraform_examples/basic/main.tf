provider "aws" {
  region = var.region
}

resource "aws_instance" "web" {
  ami           = "ami-0261755bbcb8c4a84"
  instance_type = "t2.micro"

  tags = {
    Name = "basic-web"
  }
}

resource "aws_s3_bucket" "bucket" {
  bucket = "terraguard-basic-test-12345"
}