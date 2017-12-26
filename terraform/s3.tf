resource "aws_s3_bucket" "pincushion" {
  bucket = "alexwlchan-pincushion"
  acl    = "private"

  lifecycle {
    prevent_destroy = true
  }
}
