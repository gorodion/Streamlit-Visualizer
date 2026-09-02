from omegaconf import OmegaConf
import sys
import st_pages

def main(cfg_name):
    cfg = OmegaConf.load(cfg_name)
    st_page = eval(cfg._target_)(cfg.cfg)
    st_page.run()


if __name__ == "__main__":
    cfg_name = sys.argv[1]
    main(cfg_name)
