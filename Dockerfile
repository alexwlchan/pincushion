FROM alpine

RUN apk update && apk add build-base python3 python3-dev

COPY requirements.txt /
RUN pip3 install -r /requirements.txt
