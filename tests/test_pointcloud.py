from simulocloud import PointCloud
import pytest
import numpy as np
import cPickle as pkl
import os

""" Test data """
# Data type used for arrays
_DTYPE = np.float64

@pytest.fixture
def input_list():
    """Simple [xs, ys, zs] coordinates."""
    return [[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
            [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9],
            [2.0, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9]]

@pytest.fixture
def expected_list_points():
    """The points array that should be generated from `input_list`."""
    return np.array([( 0. ,  1. ,  2. ),
                    ( 0.1,  1.1,  2.1),
                    ( 0.2,  1.2,  2.2),
                    ( 0.3,  1.3,  2.3),
                    ( 0.4,  1.4,  2.4),
                    ( 0.5,  1.5,  2.5),
                    ( 0.6,  1.6,  2.6),
                    ( 0.7,  1.7,  2.7),
                    ( 0.8,  1.8,  2.8),
                    ( 0.9,  1.9,  2.9)],
                   dtype=[('x', _DTYPE), ('y', _DTYPE), ('z', _DTYPE)])

@pytest.fixture
def expected_las_points(fname='ALS_points.pkl'):
    """The points array that should be generated from the example las data."""
    with open(abspath(fname), 'rb') as o:
        points = pkl.load(o)
    return points

""" Helper functions """

def abspath(fname, fdir='data'):
    """Return the absolute filepath of filename in (relative) directory."""
    return os.path.join(os.path.dirname(__file__), fdir, fname)

""" Test functions """

def test_PointCloud_read_directly_from_list(input_list, expected_list_points):
    """Can PointCloud initialise directly from `[xs, ys, zs]` ?"""
    assert np.all(PointCloud(input_list).points == expected_list_points)

def test_PointCloud_read_from_las(expected_las_points, fname='ALS.las'):
    """Can PointCloud be constructed from a `.las` file?"""
    assert np.all(PointCloud.from_las(abspath(fname)).points == expected_las_points)
