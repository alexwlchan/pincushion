FROM alpine

RUN apk update && apk add python3

COPY requirements.txt /
RUN pip3 install -r /requirements.txt
