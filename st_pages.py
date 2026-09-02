import numpy as np
import pandas as pd
from colour import Color
from PIL import Image, ImageDraw
from collections import defaultdict
import cv2
import cv3
import os
import plotly
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from sklearn.metrics import roc_curve
import requests
from io import BytesIO
import urllib
import random

import streamlit as st
import cv3 # pip install cv3



class DefaultPage:
    def __init__(self, cfg):
        self.page = cfg.page

    def post_init(self):
        self.init_page()

    def init_page(self):
        st.set_page_config(
            page_title=self.page.title,
            page_icon=self.page.icon,
            layout="wide",
        )
        st.markdown(f'# {self.page.title}')
        
    def run(self):
        self.post_init()

class RocPage(DefaultPage):
    def __init__(self, cfg):
        super().__init__(cfg)
        
        self.data_path = cfg.data_path

    def get_roc(self):
        df = self.df.copy()
        df = df[((df[self.scoring.cols] != -1) & (df[self.scoring.cols]).notna()).all(1)]
        df.columns = df.columns.map(self.col_format_func)
        return plotly_roc(df, self.scoring.label_col, list(map(self.col_format_func, self.scoring.cols)), title=self.scoring.roc_title)

    def update_roc_layout(self, expanded=False):
        st.plotly_chart(self.get_roc())
    
    def run(self):
        super().run()
        self.update_roc_layout()
        

class GalleryPage(DefaultPage):
    """
    Designed for simple visualization of images as a gallery
    with filtering by attributes. Also sorting supported

    Attributes:
        page (obj): Configuration object for the Streamlit page settings.
        data_path (str): Path to the data source (CSV file).
        image (obj): Configuration object for image settings (e.g., size, path column).
        attributes (obj): Configuration object for attribute settings.
        sorting (obj): Configuration object for sorting options.
        default_captions (list): Default captions to display alongside images.
        format (obj): Configuration object for formatting settings.
        advanced (dict): Advanced configuration settings.

        page_number (int): Current page number for image pagination.
        df (DataFrame): DataFrame containing the loaded data.
        curr_df (DataFrame): DataFrame containing the currently filtered data.
        columns (list): List of column names in the loaded DataFrame.
        curr_attr (str or None): Currently selected attribute for filtering.
        curr_attr_val (str or None): Currently selected attribute value for filtering.
        sort_col (str or None): Currently selected sorting column.
        is_ascending (bool or None): Sorting order (ascending or descending).
        format_funcs (dict): Dictionary of formatting functions for columns.
        col_format_func (func): Formatting function for a specific column.
        captions (list): List of selected caption columns.
        curr_seed (int or None): Current random seed for data shuffling.
        n_samples (int or None): Number of images to display on a page.
        n_cols (int or None): Number of images to display in a row.
        curr_n_samples (int or None): Number of images to display on the current page.

    Methods:
        post_init(): Perform post-initialization tasks (e.g., loading data, setting up Streamlit page).
        init_page(): Initialize the Streamlit page with custom title and icon.
        load_data(): Load data from the specified CSV file.
        init_format_funcs(): Initialize formatting functions for data columns.
        update_sidebar(): Update the sidebar with filtering options.
        update_sidebar_advanced(): Update the sidebar with advanced options.
        prepare_df(): Prepare the filtered DataFrame based on user selections.
        update_page_number(): Update the current page number based on user input.
        sample_images(): Select and display a subset of images on the page.
        draw_item(row): Draw a single image and associated information.
        draw_gallery(): Draw the entire image gallery.
        run(): Run the GalleryPage application.
    """
    def __init__(self, cfg):
        """
        Initialize a GalleryPage object with the provided configuration.

        Args:
            cfg (obj): Configuration object containing page settings and data.
        """
        self.page = cfg.page
        self.data_path = cfg.data_path
        self.image = cfg.image
        self.attributes = cfg.attributes
        self.sorting = cfg.sorting
        self.default_captions = cfg.default_captions
        self.format = cfg.format
        self.advanced = cfg.advanced

        # Initialize other instance variables
        self.page_number = 0
        self.df = None
        self.curr_df = None
        self.columns = None
        self.curr_attr = None
        self.curr_attr_val = None
        self.sort_col = None
        self.is_ascending = None
        self.format_funcs = None
        self.col_format_func = None
        self.captions = None
        self.curr_seed = None
        self.n_samples = None
        self.n_cols = None
        self.curr_n_samples = None

    # Method for post-initialization tasks
    def post_init(self):
        self.load_data()
        self.init_page()
        self.init_format_funcs()
        self.columns = self.df.columns.tolist()

    # Method for initializing the Streamlit page
    def init_page(self):
        st.set_page_config(
            page_title=self.page.title,
            page_icon=self.page.icon,
            layout="wide",
        )
        st.markdown(f'# {self.page.title}')

        # Display page description within an expander
        if self.page.description:
            with st.expander('Description', expanded=True):
                st.markdown(self.page.description)

    def _load_df(self, data_path):
        if data_path.endswith('.csv'):
            return pd.read_csv(data_path)
        if data_path.endswith('.json'):
            return pd.read_json(data_path)

    # Method for loading data frames
    def load_data(self):
        if isinstance(self.data_path, str):
            self.df = self._load_df(self.data_path)
        else:
            self.df = pd.concat(
                [self._load_df(data_path) for data_path in self.data_path], 
                ignore_index=True
            )

    # Method for initializing formatting functions for data
    def init_format_funcs(self):
        def get_format_func(fmt_mapping=None, default=None):
            if fmt_mapping is None:
                fmt_mapping = {}
            return lambda x: default if x is None else fmt_mapping.get(x, x)

        if self.format is None:
            self.col_format_func = get_format_func()
            self.format_funcs = defaultdict(lambda: get_format_func())
        else:
            self.col_format_func = get_format_func(default=self.format.default)
            self.format_funcs = defaultdict(lambda: get_format_func(default=self.format.default))
            if self.format.col_mapping is not None:
                self.col_format_func = get_format_func(dict(self.format.col_mapping), self.format.default)
            if self.format.col_val_mapping is not None:
                for col, mapping in dict(self.format.col_val_mapping).items():
                    self.format_funcs[col] = get_format_func(dict(mapping), default=self.format.default)

    # Method for updating the sidebar with filter options
    def update_sidebar(self):
        st.sidebar.title('Choose filters')

        # Attribute filter
        if self.attributes is not None:
            with st.sidebar.expander("Attribute"):
                self.curr_attr = st.selectbox(
                    "Attribute name",
                    [None] + list(self.attributes.cols),
                    format_func=self.col_format_func
                )
                # Attribute value filter (conditional on attribute selection)
                if self.curr_attr is not None:
                    self.curr_attr_val = st.selectbox(
                        "Attribute value",
                        self.df[self.curr_attr].unique().tolist(),
                        format_func=self.format_funcs[self.curr_attr]
                    )

        # Sorting options
        if self.sorting is not None:
            with st.sidebar.expander("Sorting", expanded=True):
                self.sort_col = st.selectbox(
                    "Sort by",
                    [None] + list(self.sorting.cols),
                    format_func=self.col_format_func,
                )
                # Ascending flag (conditional on sorting selection)
                if self.sort_col is not None:
                    is_ascending = False
                    if 'asc' in self.sorting:
                        if isinstance(self.sorting.asc, bool):
                            is_ascending = self.sorting.asc
                        else:
                            is_ascending = self.sorting.asc[self.sorting.cols.index(self.sort_col)]
                    self.is_ascending = st.checkbox("Ascending", value=is_ascending)

    # Method for updating the advanced options in the sidebar
    def update_sidebar_advanced(self):
        with st.sidebar.expander('Advanced'):
            # Caption selection
            self.captions = st.multiselect(
                'Caption',
                options=self.columns,
                default=self.default_captions,
                format_func=self.col_format_func
            )

            # Random seed input
            self.curr_seed = st.number_input(
                'Random seed',
                **self.advanced['random_seed']
            )

            # Max images in page slider
            self.n_samples = st.slider(
                'Max images in page',
                **self.advanced['images_in_page']
            )

            # Max images in row slider
            self.n_cols = st.slider(
                'Max images in row',
                **self.advanced['images_in_row']
            )

    # Method for preparing the filtered DataFrame based on user selections
    def prepare_df(self):
        curr_df = self.df

        if self.curr_attr is not None and self.curr_attr_val is not None:
            curr_df = curr_df[curr_df[self.curr_attr] == self.curr_attr_val]

        if self.sorting is not None and self.sort_col is not None:
            curr_df = curr_df.sort_values(self.sort_col, ascending=self.is_ascending)
        else:
            curr_df = curr_df.sample(frac=1, random_state=int(self.curr_seed))

        self.curr_df = curr_df
        return curr_df

    # Method for updating the page number based on user input
    def update_page_number(self):
        max_value = max(0, int(np.ceil(len(self.curr_df) / self.n_samples)) - 1)
        self.page_number = st.number_input(f"Page (max: {max_value})", min_value=0, max_value=max_value,
                                           value=self.page_number)

    # Method for selecting and displaying a subset of images on the page
    def sample_images(self):
        self.curr_df = self.curr_df.iloc[self.n_samples * self.page_number:
                                         self.n_samples * (self.page_number + 1)]
        self.curr_n_samples = len(self.curr_df)

    # Method for drawing a single item (image and associated information)

    def load_image(self, path):
        if path.startswith('http'):
            req = urllib.request.urlopen(path)
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
            img = cv2.imdecode(arr, -1)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img = cv3.imread(path)

        return img

    def process_image(self, img):
        if self.image.get('max_size') is not None:
            img = resize_max_size(img, self.image.max_size)
        if 'resize_height' in self.image:
            img = resize_aspect_ratio(img, height=self.image.resize_height)
        if 'resize_width' in self.image:
            img = resize_aspect_ratio(img, width=self.image.resize_width)
        return img
    
    def draw_item(self, row):
        path = row[self.image.path_col]
        img = self.load_image(path)
        img = self.process_image(img)
        st.image(img)

        if self.captions:
            st.write(
                row[self.captions]
                .rename(self.col_format_func)
                .to_dict()
            )

    # Method for drawing the entire image gallery
    def draw_gallery(self):
        if not len(self.curr_df):
            st.warning('No images found')
            return

        i = 0
        for _ in range(self.curr_n_samples // self.n_cols + 1):
            for col in st.columns(self.n_cols):
                if len(self.curr_df) == i:
                    return
                with col:
                    row = self.curr_df.iloc[i]
                    self.draw_item(row)
                i += 1

    # Method for running the GalleryPage
    def run(self):
        self.post_init()
        self.update_sidebar()
        self.update_sidebar_advanced()
        self.prepare_df()
        self.update_page_number()
        self.sample_images()
        self.draw_gallery()


def apply_filters_pandas(df, columns, format_func=None):
    from pandas.api.types import (
        is_string_dtype,
        is_numeric_dtype,
    )
    MAX_UNIQUE_VALUES = 50
    df = df.copy()

    modification_container = st.container()
    with modification_container:
        to_filter_columns = st.multiselect(
            "Filter names", 
            columns,
            format_func=format_func
        )
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            left.write("↳")
            with right:
                is_user_input = False
                if (is_string_dtype(df[column].dropna()) or is_numeric_dtype(df[column])) and df[column].nunique() < MAX_UNIQUE_VALUES:
                    uniques = df[column].unique().tolist()
                    user_cat_input = right.multiselect(
                        f"{column} values",
                        [u for u in uniques if u is not None]
                    )

                    if user_cat_input:
                        is_user_input = True
                        mask = df[column].isin(user_cat_input)

                elif is_numeric_dtype(df[column]):
                    is_user_input = True
                    _min = float(df[column].min())
                    _max = float(df[column].max())
                    step = (_max - _min) / 100
                    user_num_input = right.slider(
                        f"{column} interval",
                        _min,
                        _max,
                        (_min, _max),
                        step=step,
                    )
                    mask = df[column].between(*user_num_input)
                else:
                    user_text_input = right.text_input(
                        f"{column} substring or regex",
                    )
                    if user_text_input:
                        is_user_input = True
                        mask = df[column].str.contains(user_text_input, case=False, regex=True, na=False)

                is_exclude = st.checkbox("exclude", value=False, key=f'exclude_{column}_key')

                if is_user_input:
                    if is_exclude:
                        mask = ~mask
                    df = df[mask]
                
                if not len(df):
                    return df

    return df

class GalleryPageV2(GalleryPage):
    # Method for updating the sidebar with filter options
    def update_sidebar(self):
        st.sidebar.title('Choose options')
        # Attribute filter
        if self.attributes is None or self.attributes.get('cols') is None:
            attributes_cols = self.df.columns.tolist()
        else:
            attributes_cols = self.attributes.cols
        with st.sidebar.expander("Filters"):
            self.curr_df = apply_filters_pandas(self.df, attributes_cols, format_func=self.col_format_func)

        # Sorting options
        if self.sorting is not None:
            with st.sidebar.expander("Order"):
                self.random = st.checkbox("Randomly")
                
                self.sort_col = st.selectbox(
                    "Order by",
                    [None] + list(self.sorting.cols),
                    format_func=self.col_format_func,
                    # index=1 # by default first element
                )
                # Ascending flag (conditional on sorting selection)
                if not self.random and self.sort_col is not None:
                    is_ascending = False
                    if 'asc' in self.sorting:
                        if isinstance(self.sorting.asc, bool):
                            is_ascending = self.sorting.asc
                        else:
                            is_ascending = self.sorting.asc[self.sorting.cols.index(self.sort_col)]
                    self.is_ascending = st.checkbox("Ascending", value=is_ascending)


    # Method for preparing the filtered DataFrame based on user selections
    def prepare_df(self):
        curr_df = self.curr_df
        if self.sorting is not None and self.sort_col is not None:
            if self.random:
                k = len(curr_df)
                m = curr_df[self.sort_col].nunique()
                n = max(k // m, 1)
                
                def sample_with_replacement(group, n):
                    return group.sample(n=n, replace=(len(group) < n), random_state=1)
                
                curr_df = curr_df.groupby(self.sort_col, group_keys=False).apply(sample_with_replacement, n)
                curr_df = curr_df.sample(frac=1, random_state=int(self.curr_seed))

            else:
                curr_df = curr_df.sort_values(self.sort_col, ascending=self.is_ascending)
        else:
            curr_df = curr_df.sample(frac=1, random_state=int(self.curr_seed))

        self.curr_df = curr_df
        return curr_df


def get_scatter(x, y, name='name', showlegend=True, **kwargs):
    """
    Creates a scatter plot trace for Plotly.

    Parameters:
    - x (array-like): X-axis data points.
    - y (array-like): Y-axis data points.
    - name (str, optional): Name of the trace. Default is 'name'.
    - show_legend (bool, optional): Whether to show the trace in the legend. Default is True.
    - **kwargs: Additional keyword arguments to pass to the trace.

    Returns:
    - go.Scatter: A Plotly scatter plot trace.
    """
    return go.Scatter(
        x=x,
        y=y,
        mode='lines',
        showlegend=showlegend,
        name=name,
        # hovertemplate='%{y:.3f}',     
        **kwargs
    )


def get_roc_scatter(fpr, tpr, thr, name='name', **kwargs):
    """
    Creates a ROC curve scatter plot trace for Plotly.

    Parameters:
    - fpr (array-like): False Positive Rate values.
    - tpr (array-like): True Positive Rate values.
    - thr (array-like): Threshold values.
    - name (str, optional): Name of the trace. Default is 'name'.
    - **kwargs: Additional keyword arguments to pass to the trace.

    Returns:
    - go.Scatter: A Plotly scatter plot trace representing the ROC curve.
    """
    text = [f"{tpr_:.3f}\t\t\tthr: {thr_:.6f}"
            for fpr_, tpr_, thr_ in zip(fpr, tpr, thr)]
    return get_scatter(fpr, tpr, name=name, text=text, hovertemplate='%{text}', **kwargs)


def plotly_roc(df, label_col: str, score_cols: list, title='ROC curve'):
    """
    Creates and displays a ROC curves using Plotly.

    Parameters:
    - df (DataFrame): The DataFrame containing label and score columns.
    - label_col (str): The column name containing true labels.
    - score_cols (list): A list of column names containing score predictions.
    - title (str, optional): Title of the ROC curve plot. Default is 'ROC curve'.

    Returns:
    - go.Figure: A Plotly figure object representing the ROC curve plot.
    """
    data = []
    for i, score_col in enumerate(score_cols):
        fpr, tpr, thr = roc_curve(df[label_col], df[score_col])
        data.append(get_roc_scatter(fpr, tpr, thr, name=score_col))
    fig = go.Figure(data=data)

    fig.update_layout(
        title=title,
        xaxis_title="FPR",
        yaxis_title="TPR",
        yaxis_dtick=0.1,
        hovermode='x unified',
    )

    return fig


def get_color(label, predict):
    """
    Determines the color of bounding boxes based on prediction correctness.

    Parameters:
    - label: True label value.
    - predict: Predicted label value.

    Returns:
    - str: Color in hexadecimal format ('#RRGGBB') for the bounding box.
    """
    if predict == -1 or pd.isna(predict):
        color = Color("white").hex
        return color

    if label == predict:
        color = Color('green').hex
        return color
    else:
        color = Color('red').hex
        return color


def draw_bounds(img, color):
    """
    Draws bounding boxes on an image.

    Parameters:
    - img (PIL.Image): The PIL Image object to draw bounding boxes on.
    - color (str): Color in hexadecimal format ('#RRGGBB') for the bounding box outline.

    Returns:
    - None
    """
    draw = ImageDraw.Draw(img)
    w, h = img.size
    draw.rectangle(
        (0, 0, w, h),
        fill=None,
        outline=color,
        width=7
    )


class GalleryScoringPage(GalleryPageV2):
    """
    Designed for evaluating models' predictions and plotting ROC curves

    Attributes:
        scoring (obj): Configuration object for scoring options.

        thr (float): Current threshold for prediction binarization.
        score_col (str): Current scoring column for evaluating.
        min_val (float): Minimal value of score_col to display an item.
    """
    def __init__(self, cfg):
        super().__init__(cfg)
        self.scoring = cfg.scoring

        self.thr = None
        self.score_col = None
        self.min_val = None

    # Method to add a threshold slider
    def add_threshold_bar(self):
        """
        Adds a threshold slider to the Streamlit page.

        Allows users to adjust the threshold for binary classification.
        """
        self.thr = st.slider('Threshold', min_value=0., max_value=1., value=0.500, step=0.001, format='%3f')

    # Method to get and display the ROC curve
    def get_roc(self):
        """
        Generates and displays the ROC curve plot using Plotly.

        Returns:
        - go.Figure: A Plotly figure representing the ROC curve plot.
        """
        df = self.df.copy()
        df = df[((df[self.scoring.cols] != -1) & (df[self.scoring.cols]).notna()).all(1)]
        cols = self.scoring.cols
        label_col = self.scoring.label_col
        if self.col_format_func is not None:
            df.columns = df.columns.map(self.col_format_func)
            cols = list(map(self.col_format_func, self.scoring.cols))
            label_col = self.col_format_func(label_col)
        return plotly_roc(df, label_col, cols, title=self.scoring.roc_title)

    # Method to update the layout with the ROC chart
    def update_roc_layout(self, expanded=False):
        """
        Updates the Streamlit layout to display the ROC chart within an expander.
        """
        with st.expander('ROC', expanded=expanded):
            st.plotly_chart(self.get_roc())

    # Method to update the sidebar with scoring-related options
    def update_sidebar(self):
        """
        Overrides the parent class method to add scoring-related options to the sidebar.
        """
        super().update_sidebar()
        with st.sidebar.expander('Scoring'):
            self.score_col = st.selectbox(
                "Score column",
                self.scoring.cols,
                format_func=self.col_format_func
            )

            scores = self.df[self.score_col].dropna()
            min_val, max_val = scores.min(), scores.max()
            self.min_val = st.number_input("Score >=", min_val, max_val)

    # Method to prepare the filtered DataFrame based on user selections
    def prepare_df(self):
        """
        Overrides the parent class method to filter the DataFrame based on scoring-related selections.

        Returns:
        - DataFrame: The filtered DataFrame.
        """
        curr_df = super().prepare_df()
        curr_df = curr_df[curr_df[self.score_col] >= self.min_val]
        self.curr_df = curr_df
        return curr_df

    # Method to run the GalleryScoringPage
    def run(self):
        self.post_init()
        self.update_sidebar()
        self.update_sidebar_advanced()
        self.update_roc_layout()
        self.prepare_df()
        self.update_page_number()
        self.add_threshold_bar()
        self.sample_images()
        self.draw_gallery()

    def process_image(self, img, color, t=3):
        img = super().process_image(img)
        cv3.rectangle(img, 0., 0., 1., 1., color=color, t=t)
        return img
    
    # Method to draw each item in the gallery with colored boundaries
    # the color of boundary depends on the matching between label and prediction
    def draw_item(self, row):
        """
        Draws each item in the gallery with colored boundaries based on prediction correctness

        Parameters:
        - row: The current DataFrame row representing an item in the gallery.
        """
        path = row[self.image.path_col]
        label = row[self.scoring.label_col]
        predict = int(row[self.score_col] > self.thr)
        color = get_color(label, predict)

        img = self.load_image(path)
        img = self.process_image(img, color=color)
        st.image(img)
        
        if self.captions:
            row[self.scoring.cols] = row[self.scoring.cols].apply(np.round, args=(3,))
            st.write(
                row[self.captions]
                .rename(self.col_format_func)
                .to_dict()
            )


class GalleryPageBoxes(GalleryPageV2):
    def draw_item(self, row):
        path = row[self.image.path_col]
        img = cv3.imread(path)
        #
        # for box in row['output']['boxes']:
            # color = 'lime'
            # x1,y1,x2,y2 = box
            # cv3.rectangle(img, x1/row['width'], y1/row['height'], x2/row['width'], y2/row['height'], mode='ccwh', color=color)
        #
        if self.image.max_size is not None:
            img = resize_max_size(img, self.image.max_size)
        
        st.image(img)
        if self.captions:
            st.write(
                row[self.captions]
                .rename(self.col_format_func)
                .to_dict()
            )

class GalleryScoringPageBoxes(GalleryScoringPage):
    def draw_item(self, row):
        path = row[self.image.path_col]
        label = row[self.scoring.label_col]
        predict = int(row[self.score_col] > self.thr)
        color = get_color(label, predict)

        img = Image.open(path)
        img.thumbnail(self.image.size)
        draw_bounds(img, color)
        img = np.array(img)
        #
        for box, score in zip(row['YF3_output_stop']['boxes'], row['YF3_output_stop']['stop_score']):
            color = 'lime' if label == predict else 'red'
            x1,y1,x2,y2 = box
            cv3.rectangle(img, x1/1920, y1/1080, x2/1920, y2/1080, mode='xyxy', color=color)
            cv3.text(img, f'stop {score:.3f}', 30, 50, scale=1, t=2, color=color)
        #
        
        st.image(img)
        if self.captions:
            row[self.scoring.cols] = row[self.scoring.cols].apply(np.round, args=(3,))
            st.write(
                row[self.captions]
                .rename(self.col_format_func)
                .to_dict()
            )

class GalleryRemoteImgPage(GalleryPage):
    """
    Designed for displaying images which are on the remote server
    """
    def draw_item(self, row):
        link = row[self.image.path_col]
        if self.sorting is not None and self.sort_col is not None:
            st.write(str(row[self.sort_col]))
        st.image(link)
        st.write(row[self.captions].rename(self.col_format_func).to_dict())


def center_crop(img, new_width, new_height):
    height, width = img.shape[:2]

    left = (width - new_width) // 2
    top = (height - new_height) // 2
    right = (width + new_width) // 2
    bottom = (height + new_height) // 2

    cropped_img = img[top:bottom, left:right]

    return cropped_img
  

def get_color(label, predict):
    if predict == -1 or pd.isna(predict):
        return 'white'

    if label == predict:
        return 'green'
    else:
        return 'red'
            
class RocPage(GalleryScoringPage):
    def run(self):
        self.post_init()
        self.update_sidebar()
        self.update_sidebar_advanced()
        self.update_roc_layout(expanded=True)
        
            
def resize_max_size(img, max_size):
    h, w = img.shape[:2]
    if h <= max_size and w <= max_size:
        return img
    if h > w:
        w *= max_size / h
        h = max_size
    else:
        h *= max_size / w
        w = max_size
    img = cv3.resize(img, w, h)
    return img

def resize_aspect_ratio(image, width=None, height=None, inter=cv2.INTER_AREA):
    dim = None
    (h, w) = image.shape[:2]

    if width is None and height is None:
        return image

    if width is None:
        r = height / float(h)
        dim = (int(w * r), height)

    else:
        r = width / float(w)
        dim = (width, int(h * r))

    resized = cv2.resize(image, dim, interpolation=inter)

    return resized

            
    
class GalleryPageDetect(GalleryPage):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.det = cfg.det
  
    def draw_item(self, row):
        img = cv3.imread(row[self.image.path_col])
        if self.image.max_size is not None:
            img = resize_max_size(img, self.image.max_size)
        
        t = 0.02* np.sqrt(img.shape[0] * img.shape[1])

        c1, c2, c3, c4 = self.det.cols
        cv3.rectangle(img, row[c1], row[c2], row[c3], row[c4], mode=self.det.mode, color='lightgray', t=t)
        
        st.image(img)
        if self.captions:
            st.write(row[self.captions] \
                     .rename(self.col_format_func) \
                     .to_dict()
            )
            
class GalleryPageDetect2(GalleryPage):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.det = cfg.det
  
    def draw_item(self, row):
        img = cv3.imread(row[self.image.path_col])
        
        t = 0.02* np.sqrt(img.shape[0] * img.shape[1])
        
        for det in self.det:
            c1, c2, c3, c4 = det.cols
            if pd.isna(row[c1]):
                continue
            cv3.rectangle(img, row[c1], row[c2], row[c3], row[c4], mode=det.mode, color=det.color, t=t)
            
            if getattr(det, 'score', None) is not None:
                scr = det.score
                text = str(round(row[scr.col], scr.round))
                cv3.text(img, text, *scr.pos, color=det.color, t=t)
        
        if self.image.max_size is not None:
            img = resize_max_size(img, self.image.max_size)
        st.image(img)
        if self.captions:
            st.write(row[self.captions] \
                     .rename(self.col_format_func) \
                     .to_dict()
            )


def preprocess_redetect(img, box_in, expand_coeff=0.125, input_size=80):
    box = box_in.copy()
    height, width, _ = img.shape
    box_size = max(box[2] - box[0], box[3] - box[1])
    x1, y1, x2, y2 = np.array([max(box[0] - box_size * expand_coeff, 0),
                               max(box[1] - box_size * expand_coeff, 0),
                               min(box[2] + box_size * expand_coeff, width),
                               min(box[3] + box_size * expand_coeff, height)]).astype(int)
    crop = img[y1:y2, x1:x2]
    h, w, _ = crop.shape
    scale = input_size / max(crop.shape)

    crop = cv2.resize(crop, (int(w * scale), int(h * scale)))

    ex_crop = np.zeros((input_size, input_size, 3), dtype=np.uint8)
    h, w, _ = crop.shape
    y_begin, y_end = (input_size - h) // 2, (input_size + h) // 2
    x_begin, x_end = (input_size - w) // 2, (input_size + w) // 2
    ex_crop[y_begin:y_end, x_begin:x_end] = crop
    return ex_crop
            
class GalleryPageDetect3(GalleryPageV2):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.det = cfg.det
        
        self.detector = None

    def update_sidebar(self):
        super().update_sidebar()
        with st.sidebar.expander('Detectors'):
            self.detector = st.multiselect(
                'Detector type',
                options=[det['col'] for det in self.det],
                format_func=self.col_format_func,
                default=[self.det[0]['col']]
            )
    
    def draw_item(self, row):
        path = row[self.image.path_col]
        if path.startswith('http'):
            response = requests.get(path)
            if response.status_code != 200:
                return
            img = np.array(Image.open(BytesIO(response.content)), 'uint8')
        else:
            img = cv3.imread(row[self.image.path_col])
        
        t = 0.003 * img.shape[0]

        for det in self.det:
            if det.col not in self.detector:
                continue
            if hasattr(det, 'cols'):
                c1, c2, c3, c4 = det.cols
                if pd.isna(row[c1]):
                    continue
                cv3.rectangle(img, row[c1], row[c2], row[c3], row[c4], **det.draw_opts, t=t)
            elif det.bboxes_key is None:
                bboxes = row[det.col]
                for bbox in bboxes:
                    cv3.rectangle(img, *bbox[:4], **det.draw_opts, t=t)

                    if getattr(det, 'with_labels', None):
                        assert len(bbox) == 5 != None, 'there must be a class in bboxes'
                        mode = det.draw_opts.get('mode')
                        assert mode is None or mode.startswith('xy'), 'invalid `mode`'
                        cv3.text(img, str(bbox[4]), bbox[0], bbox[1]-0.03, color=det.draw_opts.get('color', 'lime'), t=3, scale=2)
                    if getattr(det, 'first_only', None):
                        break
                    
            else:
                    
                detection = row[det.col]
                if detection is None:
                    continue
                thr = getattr(det, 'thr', None)

                for bbox, score, label in zip(detection[det.bboxes_key], detection[det.scores_key], detection[det.labels_key]):
                    if thr is not None and score < thr:
                        continue
                        
                    if det.get('keep_labels') is not None:
                        if label not in det['keep_labels']:
                            continue
                      
                    color = det.draw_opts.get('color')
                    rel = det.draw_opts.get('rel')
                    if color is None:
                        color = cv3.COLORS[label % 50]

                    x1,y1,x2,y2 = bbox
                    bbox = x1/1280, y1/720, x2/1280, y2/720
                    cv3.rectangle(img, *bbox, color=color, mode=det.draw_opts.mode, rel=rel, t=t)

                    cls = det.get('label_mapping', {}).get(label, label)
                    
                    caption = f'{self.col_format_func(det.col)}: `{cls}`'
                    st.write(caption, score)

                    if getattr(det, 'first_only', None):
                        break

        if self.image.max_size is not None:
            img = resize_max_size(img, self.image.max_size)
        
        st.image(img)
        # st.image(img_crop)
        if self.captions:
            st.write(row[self.captions] \
                     .rename(self.col_format_func) \
                     .to_dict()
            )


class GalleryPageRedetect(GalleryPage):
    def update_sidebar(self):
        super().update_sidebar()
        with st.sidebar.expander('Detectors'):
            self.detectors = st.multiselect(
                'Detector type',
                options=['face_det_v3', 'face_det_v5'],
                default=None,
                format_func=self.col_format_func
            )
  
  
    def draw_item(self, row):
        img = cv3.imread(row[self.image.path_col])
        
        t = 0.02* np.sqrt(img.shape[0] * img.shape[1])

        cv3.rectangle(img, row.x_gt, row.y_gt, row.w_gt, row.h_gt, mode='xywh', color='lightgray', t=t)
        # if pd.notna(row.score_rd):
        #   cv3.rectangle(img, row.x_rd, row.y_rd, row.w_rd, row.h_rd, color='green' if row.score_rd > 0.1 else 'yellow', mode='xywh', t=t)
        if self.detectors:
            for detector_col in self.detectors:
                for x,y,w,h,sc in eval(row[detector_col]):
                    cv3.rectangle(img, x, y, w, h, mode='xywh', color='green' if sc > 0.1 else 'yellow', t=t)
        st.image(img)
        if self.captions:
            st.write(row[self.captions] \
                     .rename(self.col_format_func) \
                     .to_dict()
            )

 
def parse_txt_annot(annot_path, root_dir):
    data = []
    with open(annot_path) as f:
        while True:
            filename = f.readline().strip()
            if not filename:
                break
            face_cnt = int(f.readline())
            bboxes = []
            for _ in range(face_cnt):
                line = f.readline().strip()
                bbox = list(map(float, line.split()))
                bboxes.append(bbox)
                
            img_path = os.path.join(root_dir, filename)
            
            min_face_size = min(bbox[2] for bbox in bboxes) if bboxes else None
            max_face_size = max(bbox[2] for bbox in bboxes) if bboxes else None
            data.append(dict(
              img_path=img_path, 
              bboxes=bboxes, 
              n_faces=len(bboxes),
              min_face_size=min_face_size,
              max_face_size=max_face_size,
              # x_min=int(filename.split('.')[-2].split('_')[1]),
              # y_min=int(filename.split('.')[-2].split('_')[2]),
              # x_max=int(filename.split('.')[-2].split('_')[4]),
              # y_max=int(filename.split('.')[-2].split('_')[3])
            ))
    return data
            

class GalleryPageDetectTxt(GalleryPage):
    def __init__(self, cfg):
        super().__init__(cfg)

        # self.annots = None
  
    def load_data(self):
        # self.df = {}
        # for source in self.data_path:
        #     self.df[source.name] = parse_txt_annot(source.annot_file, source.root_dir)
        data = []
        for source in self.data_path:
          spam = pd.DataFrame(parse_txt_annot(source.annot_file, source.root_dir))
          spam[self.domain.col] = source.name ###
          data.append(spam)
        self.df = pd.concat(data, ignore_index=True)
  
    def update_sidebar(self):
        super().update_sidebar()
        # with st.sidebar.expander('Annotations'):
        #     self.annots = st.multiselect(
        #         'Annotation source',
        #         options=list(self.df),
        #         default=None,
        #         format_func=self.col_format_func
        #     )
  
  
    def draw_item(self, row):
        img = cv3.imread(row[self.image.path_col])
        
        t = 0.02*np.sqrt(img.shape[0] * img.shape[1])

        # cv3.rectangle(img, row.x_min, row.y_min, row.x_max, row.y_max, color='lightgray', t=t)
        for x,y,w,h,*sc in row['bboxes']:
            cv3.rectangle(img, x, y, w, h, mode='xywh', color='green', t=t)
            
        if self.image.max_size is not None:
            img = resize_max_size(img, self.image.max_size)
        st.image(img)
        if self.captions:
            st.write(row[self.captions] \
                     .rename(self.col_format_func) \
                     .to_dict()
            )


colors = plotly.colors.qualitative.Dark24

def plotly_multirocs(df, group_cols, score_cols, n=2, label_col='label', title='ROC curves', save_path=None):
    groups = group_cols
    if isinstance(n, int):
        rows = cols = n
    else:
        rows, cols = n
    fig = make_subplots(rows=n, cols=n, subplot_titles=groups)
    for num_plot, group_col in enumerate(groups):
        data = df[df[group_col] == 1]
        assert len(data), f'All zeros in column `{group_col}`'
        for i, score_col in enumerate(score_cols):
            if (data[score_col].isna() | data[score_col].eq(-1)).all():
                continue
            # if (data[score_col].isna() | data[score_col].eq(-1)).mean() > 0.2:
            #     continue
            fpr, tpr, thr = roc_curve(data[label_col], data[score_col])
            fig.add_trace(
                get_roc_scatter(fpr, tpr, thr, name=score_col, showlegend=num_plot==0, legendgroup=score_col, line_color=colors[i % len(colors)]),
                row=num_plot//n+1, col=num_plot%n+1,
            )
    fig.update_xaxes(range=[0, 0.01])
    fig.update_layout(
        title=title,
        xaxis_title="FPR",
        yaxis_title="TPR",
        yaxis_dtick=0.1,
        hovermode='x unified',
        # width=800,
        # height=600,
        xaxis4_range=[0,0.4],
        xaxis5_range=[0,0.4],
        xaxis6_range=[0,0.4]
      
    )
    if save_path is not None:
        fig.write_html(save_path)
    
    return fig
  
  
  
class MultiRocPage(DefaultPage):
    def __init__(self, cfg):
        super().__init__(cfg)
        
        self.data_path = cfg.data_path
        self.roc = cfg.roc
        
    def load_data(self):
        self.df = pd.read_csv(self.data_path)
        
    def post_init(self):
        super().post_init()
        self.load_data()
        self.columns = self.df.columns.tolist()

    def get_roc(self):
        df = self.df.copy()
        # df = df[((df[self.roc.score_cols] != -1) & (df[self.roc.score_cols]).notna()).all(1)]
        return plotly_multirocs(df, **self.roc)
        # df.columns = df.columns.map(self.col_format_func)
        # return plotly_roc(df, self.scoring.label_col, list(map(self.col_format_func, self.scoring.cols)), title=self.scoring.roc_title)

    def update_roc_layout(self):
        st.plotly_chart(self.get_roc())
    
    def run(self):
        super().run()
        self.update_roc_layout()
        
    # def add_threshold_bar(self):
    #     self.thr = st.slider('Threshold', min_value=0., max_value=1., value=0.500, step=0.001, format='%3f')


class LabelingPageV2(GalleryPageV2):
    def __init__(self, cfg):
        super().__init__(cfg)

        self.labeling = cfg.labeling

        self.label = None
        self.row = None
        self.annotator = None

    def update_sidebar(self):
        if 'annotators' in self.labeling:
            with st.container(border=True):
                self.annotator = st.selectbox(
                    'Choose annotator',
                    [None] + list(self.labeling.annotators)
                )
            if self.annotator is not None:
                self.df = self.df[self.df[self.annotator]]
        
        super().update_sidebar()
    
    def update_sidebar_advanced(self):
        with st.sidebar.expander('Advanced'):
            self.captions = st.multiselect(
                'Caption',
                options=list(self.columns),
                default=list(getattr(self, 'default_captions') or []),
                format_func=self.col_format_func
            )

            self.curr_seed = st.number_input(
                'Random seed',
                **self.advanced['random_seed']
            )

    def _default_class(self):
        # current_label = st.session_state['result_data'].get(row[self.image.path_col])
        st.session_state['current_label'] = None
        
    
    def update_page_number(self):
        max_value = max(0, len(self.curr_df)-1)
        self.page_number = st.number_input(f"Page (max: {max_value})", min_value=0, max_value=max_value,
                                           value=self.page_number, on_change=self._default_class)
      
    def sample_images(self):
        # essentially we sample only one image
        self.curr_df = self.curr_df.iloc[[self.page_number]]
        self.curr_n_samples = len(self.curr_df)

    def init_collector(self):
        if 'result_data' not in st.session_state:
            st.session_state['result_data'] = {}

    def add_captions(self, row):
        if self.captions:
            st.write(
                row[self.captions]
                .rename(self.col_format_func)
                .to_dict()
            )
    
    def draw_gallery(self):
        if not len(self.curr_df):
            st.warning('No images found')
            return

        # curr_df contains only one image
        row = self.row = self.curr_df.iloc[0]

        if getattr(self.page, 'as_columns', True):
            c1, c2 = st.columns((2, 1))
            with c1:
                self.draw_item(row)
            with c2:
                self.add_class_box(row)
        else:
            self.draw_item(row)
            self.add_class_box(row)
        self.add_captions(row)

    def _update_class(self):
        new_label = st.session_state['current_label']
        img_path = self.row[self.image.path_col]
        st.session_state['result_data'][img_path] = new_label

  
    def add_class_box(self, row):   
        options = [None] + self.labeling.classes
        
        self.label = st.radio(
            'Class',
            options=options,
            key='current_label',
            on_change=self._update_class
        )

        current_label = st.session_state['result_data'].get(row[self.image.path_col])
        if current_label:
            st.info(f'Picked: {current_label}')
        

    def _save_csv(self):
        save_path = self.labeling.save_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        pd.Series(st.session_state['result_data']).to_csv(save_path)
        st.info('Annotations successfully saved')
  
    def export_results(self):
        if not len(st.session_state['result_data']):
            return
        ser = pd.Series(st.session_state['result_data'])
        # st.table(ser)
        c1, _, c2 = st.columns((1, 6, 1))
        if self.labeling.save_path:
            with c1:
                st.button('Save', on_click=self._save_csv)
        with c2:
            st.download_button('Export CSV', ser.to_csv(), file_name='annotation.csv')

    def run(self):
        self.post_init()
        self.update_sidebar()
        self.update_sidebar_advanced()
        if self.annotator is not None:
            self.prepare_df()
            self.update_page_number()
            self.sample_images()
            self.init_collector()
            self.draw_gallery()
            self.export_results()
        else:
            st.warning('Choose annotator')



class VideoGalleryPage(GalleryPageV2):
    def draw_item(self, row):
        url = row[self.image.path_col]
        st.video(url)


class LabelingVideoPage(VideoGalleryPage, LabelingPageV2):
    pass


class MultiLabelingPage(LabelingPageV2):
    def init_collector(self):
        if 'result_data' not in st.session_state:
            st.session_state['result_data'] = defaultdict(dict)
  
    def _default_class(self):
        for info in self.labeling.classes:
            if 'type' in info and info.type == 'checkbox':
                new_value = False
            else:
                new_value = None
            st.session_state[f'current_label_{info["name"]}'] = new_value

    def add_class_box(self, row):
        def update_state_wrapper(name, key):
            def update_class():
                new_label = st.session_state[key]
                id = self.row[self.labeling.id_key]
                st.session_state['result_data'][id][name] = new_label
            return update_class
          
        for info in self.labeling.classes:
            key = f'current_label_{info["name"]}'
            if 'type' in info and info.type == 'checkbox':
                options = info['options']
                self.label = st.checkbox(
                    info['name'],
                    key=key,
                    on_change=update_state_wrapper(info["name"], key)
                )
            else:
                options = [None] + info['options']
                self.label = st.radio(
                    info["name"],
                    options=options,
                    key=key,
                    on_change=update_state_wrapper(info["name"], key)
                )

        current_label = st.session_state['result_data'].get(row[self.image.path_col])
        if current_label:
            st.info(f'Picked: {current_label}')
  
    def export_results(self):
        if not len(st.session_state['result_data']):
            return
        ser = pd.DataFrame(st.session_state['result_data']).T
        # st.table(ser)
        c1, _, c2 = st.columns((1, 6, 1))
        # if self.labeling.save_path:
        #     with c1:
        #         st.button('Save', on_click=self._save_csv)
        with c2:
            st.download_button('Export CSV', ser.to_csv(), file_name='annotation.csv')



class MultiLabelingPageDB(MultiLabelingPage):
    def __init__(self, cfg):
        super().__init__(cfg)
        
        from database import AnnotationDatabase
        self.DB = AnnotationDatabase()
    
    def init_collector(self):
        # if 'result_data' not in st.session_state:
        #     st.session_state['result_data'] = defaultdict(dict)
        pass
  
    def _default_class(self):
        for info in self.labeling.classes:
            if 'type' in info and info.type == 'checkbox':
                new_value = False
            else:
                new_value = None
            st.session_state[f'current_label_{info["name"]}'] = new_value

    def _get_nickname(self):
        if self.annotator is None:
            return 'noname'
        return self.annotator
    
    def add_class_box(self, row):
        def update_state_wrapper(name, key):
            def update_class():
                new_label = st.session_state[key]
                nickname = self._get_nickname()
                project_name = self.labeling.project_name
                id = self.row[self.labeling.id_key]
                with self.DB as db:
                    annotation = db.get_annotation(nickname, project_name, task_id=id)
                    if annotation is None:
                        db.add_annotation(
                            nickname, 
                            project_name, 
                            task_id=id, 
                            info={name: new_label}
                        )
                    else:
                        if new_label is None:
                            return
                        if annotation.info is None:
                            annotation.info = {}
                        new_info = annotation.info.copy()
                        new_info[name] = new_label
                        annotation.info = new_info

                    print('UPDATED INFO:', nickname, id, db.get_annotation_info(nickname, project_name, task_id=id))
                # st.session_state['result_data'][img_path][name] = new_label
            return update_class
          
        for info in self.labeling.classes:
            key = f'current_label_{info["name"]}'
            if 'type' in info and info.type == 'checkbox':
                options = info['options']
                self.label = st.checkbox(
                    info['name'],
                    key=key,
                    on_change=update_state_wrapper(info["name"], key)
                )
            elif 'type' in info and info['type'] == 'text':
                self.label = st.text_input(
                    info['name'],
                    value=None,
                    key=key,
                    on_change=update_state_wrapper(info["name"], key)
                )
            else:
                options = [None] + list(info['options'])
                self.label = st.radio(
                    info["name"],
                    options=options,
                    key=key,
                    on_change=update_state_wrapper(info["name"], key)
                )

        # current_label = st.session_state['result_data'].get(row[self.image.path_col])
        with self.DB as db:
            current_info = db.get_annotation_info(nickname=self._get_nickname(), project_name=self.labeling.project_name, task_id=row[self.labeling.id_key])
        if current_info:
            st.info(f'Picked: {current_info}')
  
    def export_results(self):
        # ser = pd.DataFrame(st.session_state['result_data']).T
        with self.DB as db:
            annotations = db.get_annotations_by_project_worker(project_name=self.labeling.project_name, nickname=self._get_nickname())
            data = [dict(task_id=annotation.task_id, info=annotation.info) for annotation in annotations]

        if not len(data):
            return
        df = pd.DataFrame(data)
        # st.table(ser)
        c1, _, c2 = st.columns((1, 6, 1))
        # if self.labeling.save_path:
        #     with c1:
        #         st.button('Save', on_click=self._save_csv)
        with c2:
            st.download_button('Export CSV', df.to_csv(), file_name='annotation.csv')


class SbSLabelingPageDB(MultiLabelingPageDB):
    def draw_item(self, row):
        path = row[['url_1']]
        img1 = self.load_image(row['url_1'])
        img1 = self.process_image(img1)

        img2 = self.load_image(row['url_2'])
        img2 = self.process_image(img2)
        
        col1, col2 = st.columns(2)
        with col1:
            st.text('Изображение ДО:')
            st.image(img1)
        with col2:
            st.text('Изображение ПОСЛЕ:')
            st.image(img2)

        if self.captions:
            st.write(
                row[self.captions]
                .rename(self.col_format_func)
                .to_dict()
            )

    def add_class_box(self, row):
        def update_state_wrapper(name, key):
            def update_class():
                new_label = st.session_state[key]
                nickname = self._get_nickname()
                project_name = self.labeling.project_name
                id = self.row[self.labeling.id_key]
                with self.DB as db:
                    annotation = db.get_annotation(nickname, project_name, task_id=id)
                    if annotation is None:
                        db.add_annotation(
                            nickname, 
                            project_name, 
                            task_id=id, 
                            info={name: new_label}
                        )
                    else:
                        if annotation.info is None:
                            annotation.info = {}
                        new_info = annotation.info.copy()
                        new_info[name] = new_label
                        annotation.info = new_info

                    print('UPDATED INFO:', nickname, id, db.get_annotation_info(nickname, project_name, task_id=id))
                # st.session_state['result_data'][img_path][name] = new_label
            return update_class
          
        for info in self.labeling.classes:
            key = f'current_label_{info["name"]}'
            answers = [row['answer_1'], row['answer_2']]
            random.shuffle(answers)
            options = [None] + answers + ['Оба хорошо', 'Оба плохо']
            self.label = st.radio(
                info["name"],
                options=options,
                key=key,
                on_change=update_state_wrapper(info["name"], key)
            )

        # current_label = st.session_state['result_data'].get(row[self.image.path_col])
        with self.DB as db:
            current_info = db.get_annotation_info(nickname=self._get_nickname(), project_name=self.labeling.project_name, task_id=row[self.labeling.id_key])
        if current_info:
            st.info(f'Picked: {current_info}')
        
class MultiLabelingVideoPageDB(VideoGalleryPage, MultiLabelingPageDB):
    pass

class SpamPage(GalleryPage):
    def run(self):
        st.image('https://storage.mds.yandex.net:443/get-voicetoloka/10843900/2ff702d4-4362-4e07-b391-ec9a0f124fea')


class GalleryRecPage(GalleryPageV2):
    def draw_item(self, row):
        path1, path2 = row[self.image.path_col]
        img1 = self.process_image(self.load_image(path1))
        img2 = self.process_image(self.load_image(path2))
    
        img = np.concatenate((img1, img2), axis=1)
        st.image(img)
    
        if self.captions:
            st.write(
                row[self.captions]
                .rename(self.col_format_func)
                .to_dict()
            )


class GalleryRecScoringPage(GalleryScoringPage):
    def draw_item(self, row):
        path = row[self.image.path_col]
        label = row[self.scoring.label_col]
        predict = int(row[self.score_col] > self.thr)
        color = get_color(label, predict)

        img1 = self.load_image(path[0])
        img2 = self.load_image(path[1])
        img1 = GalleryPageV2.process_image(self, img1)
        img2 = GalleryPageV2.process_image(self, img2)

        img = np.concatenate((img1, img2), axis=1)
        
        img = self.process_image(img, color=color)
        st.image(img)
        
        if self.captions:
            row[self.scoring.cols] = row[self.scoring.cols].apply(np.round, args=(3,))
            st.write(
                row[self.captions]
                .rename(self.col_format_func)
                .to_dict()
            )


class RankedVideoGalleryPage(VideoGalleryPage):
    """
    Галерея видео с поддержкой выбора релевантной выдачи по предварительному ранжированию.
    - ranking_path загружается в load_data
    - имена столбцов (query_key, ranked_list_key) настраиваемые
    - блок Relevance Search в основном окне
    - в Sidebar — выбор столбца ranked_list из ranking_df
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self.ranking_config = cfg.ranking

        # Эти поля будут инициализированы в load_data
        self.ranking_path = None
        self.ranking_df = None
        self.query_key = None
        self.ranked_list_key = None
        self.ranking_order = None

        self.selected_query = None
        self.selected_ranking_col = None  # Выбранный столбец с ranked_list

    def load_data(self):
        super().load_data()

        # Инициализируем параметры из ranking-конфига
        self.ranking_path = self.ranking_config.ranking_path
        self.query_key = self.ranking_config.get("query_key", "query")
        self.ranked_list_key = self.ranking_config.get("ranked_list_key", "ranked_list")
        self.ranking_order = self.ranking_config.get("order", "most_relevant_first")

        # Загружаем ranking_df
        if self.ranking_path.endswith('.csv'):
            self.ranking_df = pd.read_csv(
                self.ranking_path,
                converters={self.ranked_list_key: ast.literal_eval}
            )
        elif self.ranking_path.endswith('.json'):
            self.ranking_df = pd.read_json(self.ranking_path)
            if not isinstance(self.ranking_df.iloc[0][self.ranked_list_key], list):
                self.ranking_df[self.ranked_list_key] = self.ranking_df[self.ranked_list_key].apply(ast.literal_eval)
        else:
            raise ValueError(f"Unsupported ranking file format: {self.ranking_path}")

        # Проверка обязательных столбцов
        if self.query_key not in self.ranking_df.columns:
            raise ValueError(f"Column '{self.query_key}' not found in ranking_df")

    def update_sidebar(self):
        super().update_sidebar()  # Оставляем фильтры из GalleryPageV2

        # 🔹 Новый блок: Ranking
        with st.sidebar.expander("Ranking", expanded=True):
            st.markdown("### 📊 Select Ranking Source")

            # Получаем все столбцы, которые могут содержать ranked_list (списки)
            list_columns = [
                col for col in self.ranking_df.columns
                if col != self.query_key and isinstance(self.ranking_df[col].dropna().iloc[0], list)
            ]

            # Добавляем None как опцию (использовать default из конфига)
            options = [None] + list_columns
            default_index = 0 if self.ranked_list_key not in list_columns else list_columns.index(self.ranked_list_key) + 1

            self.selected_ranking_col = st.selectbox(
                "Ranking column",
                options=options,
                format_func=lambda x: "Default" if x is None else str(x),
                index=default_index,
                help=f"Select column containing ranked lists. Default: '{self.ranked_list_key}'"
            )

            # Если выбрано None — используем значение из конфига
            self.active_ranked_list_col = self.selected_ranking_col or self.ranked_list_key

            if self.active_ranked_list_col not in self.ranking_df.columns:
                st.error(f"Column '{self.active_ranked_list_col}' not found in ranking data.")
                st.stop()

            # Проверяем, что значения — списки
            sample_val = self.ranking_df[self.active_ranked_list_col].dropna().iloc[0]
            if not isinstance(sample_val, list):
                st.error(f"Column '{self.active_ranked_list_col}' must contain lists of indices.")
                st.stop()

    def init_page(self):
        super().init_page()

        # 🔹 Блок Relevance Search — в основном потоке, после описания
        st.markdown("### 🔍 Relevance Search")
        queries = [None] + self.ranking_df[self.query_key].tolist()
        self.selected_query = st.selectbox(
            "Select trigger",
            options=queries,
            format_func=lambda x: "Default gallery (no ranking)" if x is None else str(x),
            key="selected_query"
        )
        st.text("")

    def prepare_df(self):
        if self.selected_query is not None:
            row = self.ranking_df[self.ranking_df[self.query_key] == self.selected_query].iloc[0]
            ranked_indices = row[self.active_ranked_list_col]  # Используем выбранный столбец

            # Проверка: все индексы должны быть int и в пределах df
            if not all(isinstance(idx, (int, np.integer)) for idx in ranked_indices):
                raise ValueError(f"All indices in '{self.active_ranked_list_col}' must be integers.")

            # Определяем порядок сортировки
            if self.ranking_order == "least_relevant_first":
                # Предполагается, что ranked_list начинается с наименее релевантных → инвертируем
                ranked_indices = ranked_indices[::-1]
            elif self.ranking_order == "most_relevant_first":
                # Оставляем как есть
                pass
            else:
                raise ValueError(
                    f"Unknown order: {self.ranking_order}. Use 'most_relevant_first' or 'least_relevant_first'"
                )

            # Фильтруем основной df по индексам
            try:
                filtered_df = self.df.iloc[ranked_indices].copy()
            except IndexError as e:
                raise IndexError(f"Invalid index in '{self.active_ranked_list_col}': {e}")

            self.curr_df = filtered_df.reset_index(drop=True)
        else:
            # Используем стандартную логику фильтрации и случайного порядка
            super().prepare_df()

    def update_page_number(self):
        if self.curr_df is None or len(self.curr_df) == 0:
            max_page = 0
        else:
            max_page = max(0, (len(self.curr_df) - 1) // self.n_samples)

        self.page_number = st.number_input(
            f"Page (0 to {max_page})",
            min_value=0,
            max_value=max_page,
            value=self.page_number
        )

    def sample_images(self):
        start_idx = self.page_number * self.n_samples
        end_idx = start_idx + self.n_samples
        self.curr_df = self.curr_df.iloc[start_idx:end_idx].reset_index(drop=True)
        self.curr_n_samples = len(self.curr_df)

    def run(self):
        self.post_init()

        # Sidebar: фильтры и настройки
        self.update_sidebar()
        self.update_sidebar_advanced()

        # Основной поток: Relevance Search и галерея
        self.prepare_df()
        self.update_page_number()
        self.sample_images()
        self.draw_gallery()


class SbSPageV2(MultiLabelingPageDB):
    """
    Side-by-Side (SbS) labeling page with model answers display and star ratings.
    Inherits from MultiLabelingPageDB to handle database storage.
    """
    def draw_item(self, row):
        """
        Renders the visual content (Image/Video/None) and Model Answers.
        Layout:
        1. Optional Question
        2. Visual Content (Image or Video)
        3. Model Answers (Two columns: Model A / Model B)
        """
        
        # 1. Optional Question
        question_key = getattr(self.labeling, 'question_key', None)
        if question_key and question_key in row:
            question_text = row[question_key]
            if pd.notna(question_text):
                st.markdown(f"### ❓ {question_text}")
                st.markdown("---")

        # 2. Visual Content (Image / Video / None)
        # Determine type from config, default to 'image' if not specified but path exists
        media_type = getattr(self.image, 'type', 'image') 
        path_col = self.image.path_col
        
        if path_col and path_col in row and pd.notna(row[path_col]):
            path = row[path_col]
            
            with st.container(width=500):
                if media_type == 'video':                
                    st.video(path)
                elif media_type == 'image':
                    try:
                        img = self.load_image(path)
                        img = self.process_image(img)
                        st.image(img)
                    except Exception as e:
                        st.error(f"Error loading image: {e}")
                else:
                    st.warning(f"Unknown media type: {media_type}")
        else:
            pass
            # Visual content is absent (path_col is null or value is missing)
            # st.info("No visual content provided for this item.")
        
        st.markdown("---")

        # 3. Model Answers Display
        # Keys from config
        model_a_key = getattr(self.labeling, 'model_A_key', 'model_A_answer')
        model_b_key = getattr(self.labeling, 'model_B_key', 'model_B_answer')
        
        answer_a = row.get(model_a_key, "No answer")
        answer_b = row.get(model_b_key, "No answer")

        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("**Модель А:**")
            st.write(answer_a)
            
        with col_b:
            st.markdown("**Модель B:**")
            st.write(answer_b)

    def add_class_box(self, row):
        """
        Renders the labeling forms (Star Ratings) under the model answers.
        Layout: Two columns matching the answers above.
        Saves to DB via MultiLabelingPageDB logic.
        """
        
        # Helper to wrap DB update logic for star rating changes
        def update_state_wrapper(name, key):
            def update_class():
                new_label = st.session_state[key]
                nickname = self._get_nickname()
                project_name = self.labeling.project_name
                id = self.row[self.labeling.id_key]
                with self.DB as db:
                    annotation = db.get_annotation(nickname, project_name, task_id=id)
                    if annotation is None:
                        db.add_annotation(
                            nickname, 
                            project_name, 
                            task_id=id, 
                            info={name: new_label}
                        )
                    else:
                        if new_label is None:
                            return
                        if annotation.info is None:
                            annotation.info = {}
                        new_info = annotation.info.copy()
                        new_info[name] = new_label
                        annotation.info = new_info

                    print('UPDATED INFO:', nickname, id, db.get_annotation_info(nickname, project_name, task_id=id))
                # st.session_state['result_data'][img_path][name] = new_label
            return update_class
          
        # Create two columns for the star ratings
        col_rate_a, col_rate_b = st.columns(2)

        for i, info in enumerate(self.labeling.classes):
            key_base = f'current_label_{info["name"]}'
            key_a = f"{key_base}_A"
            key_b = f"{key_base}_B"

            name_a = f"{info['name']}_A"
            name_b = f"{info['name']}_B"
            
            if info['type'] == 'star_rating':
                with col_rate_a:
                    st.feedback(
                        options='stars', 
                        key=key_a, 
                        # default=None,
                        on_change=update_state_wrapper(name_a, key_a)
                    )
                
                with col_rate_b:
                    st.feedback(
                        options='stars', 
                        key=key_b, 
                        # default=None,
                        on_change=update_state_wrapper(name_b, key_b)
                    )
            # TODO common builder for every type of form
            elif info['type'] == 'text':
                with col_rate_a:
                    st.text_input(
                        info['name'],
                        value=None,
                        key=key_a,
                        on_change=update_state_wrapper(name_a, key_a)
                    )
                with col_rate_b:
                    st.text_input(
                        info['name'],
                        value=None,
                        key=key_b,
                        on_change=update_state_wrapper(name_b, key_b)
                    )
        

        # Display current saved info from DB
        with self.DB as db:
            current_info = db.get_annotation_info(
                nickname=self._get_nickname(), 
                project_name=self.labeling.project_name, 
                task_id=row[self.labeling.id_key]
            )
        if current_info:
            with st.expander("Текущие сохраненные данные", expanded=True):
                st.json(current_info)

    def _default_class(self):
        """Reset session state for star ratings when moving to next item."""
        for info in self.labeling.classes:
            key_base = f'current_label_{info["name"]}'
            key_a = f"{key_base}_A"
            key_b = f"{key_base}_B"
            
            if 'type' in info and info.type == 'checkbox':
                new_value = False
            else:
                new_value = None
            st.session_state[key_a] = new_value
            st.session_state[key_b] = new_value