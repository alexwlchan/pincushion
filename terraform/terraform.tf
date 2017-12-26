terraform {
  required_version = ">= 0.9"

  backend "s3" {
    bucket         = "alexwlchan-infra"
    key            = "pincushion.tfstate"
    dynamodb_table = "terraform-locktable"
    region         = "eu-west-1"
  }
}
