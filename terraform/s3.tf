resource "aws_s3_bucket" "pincushion" {
  bucket = "alexwlchan-pincushion"
  acl    = "private"

  lifecycle {
    prevent_destroy = true
  }
}

data "aws_iam_policy_document" "s3_access" {
  statement {
    actions = [
      "s3:*",
      "s3:List*",
    ]

    resources = [
      "${aws_s3_bucket.pincushion.arn}/*",
    ]
  }
}

resource "aws_iam_user" "linode" {
  name = "linode"
}

resource "aws_iam_access_key" "linode" {
  user    = "${aws_iam_user.linode.name}"
}

resource "aws_iam_user_policy" "linode" {
  user   = "${aws_iam_user.linode.name}"
  policy = "${data.aws_iam_policy_document.s3_access.json}"
}

output "linode_key_id" {
  value = "${aws_iam_access_key.linode.id}"
}

output "linode_key_secret" {
  value = "${aws_iam_access_key.linode.secret}"
}
