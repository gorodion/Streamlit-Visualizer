#!/bin/bash

CONFIG=$1
PORT=$2
HOST=::

streamlit run app.py \
            --server.address $HOST \
            --server.port $PORT \
            $CONFIG
