from omegaconf import OmegaConf
import sys
import os
from glob import glob
import streamlit as st

import st_pages

CONFIG_DIR = 'configs'
# DEFAULT_CONFIG = '{}/default.yaml'.format(CONFIG_DIR)
DEFAULT_CONFIG = 'default'

def add_config_switcher(config_names):
    with st.expander('Config list', expanded=False):
        st.radio(
            "Choose config",
            config_names,
            # format_func=lambda x: os.path.relpath(x, CONFIG_DIR).replace('.yaml', ''),
            key='cfg'
        )

def extract_config_name(q_params):
    cfg_name = q_params['cfg']
    return cfg_name
    # if not cfg_name.endswith('.yaml'):
    #     cfg_name += '.yaml'
    # if not cfg_name.startswith(CONFIG_DIR):
    #     cfg_name = os.path.join(CONFIG_DIR, cfg_name)
    # return cfg_name

# from hydra.core.global_hydra import GlobalHydra
from hydra import compose, initialize
from hydra.utils import instantiate

def get_config(cfg_name):
    # hydra._internal.hydra.GlobalHydra.get_state().clear()
    # GlobalHydra.instance().clear()
    with initialize(config_path="configs", job_name="streamlit-page", version_base='1.1'):
        cfg = compose(config_name=cfg_name, overrides=sys.argv[1:])
        return cfg


def main():
    # config_names = sorted(os.path.join(CONFIG_DIR, i) for i in os.listdir(CONFIG_DIR) if i.endswith('.yaml') if not i.startswith('__'))
    config_names = sorted(i.replace('.yaml', '') for i in os.listdir(CONFIG_DIR) if i.endswith('.yaml') if not i.startswith('__'))
    if 'cfg' not in st.session_state:
        if 'cfg' in st.query_params:
            q_params = st.query_params
            cfg_name = extract_config_name(q_params)
            st.session_state['cfg'] = cfg_name
        else:
            st.session_state['cfg'] = DEFAULT_CONFIG
    cfg_name = st.session_state['cfg']
    # cfg = OmegaConf.load(cfg_name)
    cfg = get_config(cfg_name)
    st_page = instantiate(cfg)
    # st_page = eval(cfg._target_)(cfg.cfg)
    try:
        st_page.run()
    finally:
        if 'cfg' not in st.query_params:
            st.write('\n')
            st.write('\n')
            st.divider()
            add_config_switcher(config_names)
      


if __name__ == "__main__":
    main()
