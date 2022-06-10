FROM python:3.10-alpine

RUN pip3 install --upgrade pip
RUN pip3 install aiohttp requests aiohttp-retry
COPY ./aws_sso_url_generator.py /usr/local/bin/aws_sso_url_generator
RUN adduser -h /home/user -s /bin/bash -D user
USER user
ENTRYPOINT ["python", "/usr/local/bin/aws_sso_url_generator"]
