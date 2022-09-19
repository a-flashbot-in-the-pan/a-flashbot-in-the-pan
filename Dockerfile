FROM ubuntu:18.04

MAINTAINER Christof Torres (christof.torres@inf.ethz.ch)

SHELL ["/bin/bash", "-c"]
RUN apt-get update -q && \
    apt-get install -y \
    wget curl unzip software-properties-common python3-distutils python3-pip python3-apt python3-dev iputils-ping && \
    apt-get clean -q && rm -rf /var/lib/apt/lists/*

# Install MongoDB
ARG DEBIAN_FRONTEND=noninteractive
RUN wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add && echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list && apt-get update && apt-get install -y mongodb-org

# Install Python Dependencies
RUN add-apt-repository -y ppa:deadsnakes && \
    apt-get install -y --no-install-recommends python3.8-venv python3.8-dev && \
    apt-get clean -q && rm -rf /var/lib/apt/lists/*
RUN python3.8 -m venv /venv
ENV PATH=/venv/bin:$PATH
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
RUN rm requirements.txt

# Install Node.js
RUN curl -sL https://deb.nodesource.com/setup_12.x | bash -
RUN apt-get update -q && \
    apt-get install -y nodejs && \
    apt-get clean -q && rm -rf /var/lib/apt/lists/*

WORKDIR /root
COPY data-collection data-collection

# Install Node.js dependencies
WORKDIR /root/data-collection/pending-transactions
RUN npm install

# Download token prices
RUN gdown https://drive.google.com/uc?id=1zSrz6-GuXqDX3qa_rLVlZTte-Kubz_uE
RUN unzip prices.zip
RUN rm prices.zip
RUN mv prices.json /root/data-collection/mev/utils/

WORKDIR /root
COPY analysis analysis
