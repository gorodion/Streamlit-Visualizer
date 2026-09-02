#!/bin/bash

PORT=$1
HOST=::

streamlit run app_master.py \
            --server.address $HOST \
            --server.port $PORT
