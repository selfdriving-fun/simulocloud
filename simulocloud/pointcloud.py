"""
pointcloud

Read in and store point clouds.
"""

import numpy as np
import string
import laspy.file
import laspy.header
import collections
import simulocloud.exceptions

_HEADER_DEFAULT = {'data_format_id': 3,
                   'x_scale': 2.5e-4,
                   'y_scale': 2.5e-4,
                   'z_scale': 2.5e-4,
                   'software_id': "simulocloud"[:32].ljust(32, '\x00'),
                   'system_id': "CREATION"[:32].ljust(32, '\x00')}

_VLR_DEFAULT = {'user_id': 'LASF_Projection\x00',
               'record_id': 34735,
               'VLR_body': ('\x01\x00\x01\x00\x00\x00\x03\x00\x01\x04\x00'
                            '\x00\x01\x00\x02\x00\x00\x04\x00\x00\x01\x00'
                            '\x03\x00\x00\x08\x00\x00\x01\x00\xe6\x10'),
               'description': 'GeoKeyDirectoryTag (mandatory)\x00\x00',
               'reserved': 43707}

_DTYPE = np.float64

class PointCloud(object):
    """ Contains point cloud data """
    
    dtype = _DTYPE

    def __init__(self, xyz, header=None):
        """Create PointCloud with 3D point coordinates stored in a (3*n) array.
        
        Arguments
        ---------
        xyz: sequence of len 3
            equal sized sequences specifying 3D point coordinates (xs, ys, zs)
        header: laspy.header.Header instance
            base header to use for output
        
        Example
        -------
        >>> from numpy.random import rand
        >>> n = 5 # number of points
        >>> x, y, z = rand(n)*100, rand(n)*100., rand(n)*20
        >>> pc = PointCloud((x,y,z))
        >>> pc.points
        array([( 75.37742432,  20.33372458,  14.73631503),
               ( 39.34924712,  29.56923584,  12.15410051),
               ( 37.11597209,  47.5210436 ,   7.08069784),
               ( 46.30703381,  62.75060038,  17.70324372),
               ( 25.92662908,  55.45793312,   5.95560623)], 
              dtype=[('x', '<f8'), ('y', '<f8'), ('z', '<f8')])
        
        Notes
        -----
        The use of the constructor methods (`PointCloud.from...`) is preferred.
        """
        # Coerce None to empty array
        if xyz is None:
            xyz = [[], [], []]
        
        # Store points as 3*n array
        x, y, z = xyz # ensure only 3 coordinates
        self._arr = np.stack([x, y, z])

        if header is not None:
            self._header = header

    def __len__(self):
        """Number of points in point cloud"""
        return self._arr.shape[1]

    def __add__(self, other):
        """Concatenate two PointClouds."""
        return type(self)(np.concatenate([self._arr, other.arr], axis=1))

    """ Constructor methods """
 
    @classmethod
    def from_las(cls, *fpaths, **kwargs):
        """Initialise PointCloud from one or more .las files.
    
        Arguments
        ---------
        *fpaths: str
            filepaths of .las file containing 3D point coordinates
        bounds: `Bounds` or similiar (optional)
            if supplied, pointcloud will contain only points within `bounds
        allow_empty: bool
            if `bounds` specified, allows resultant pointcloud to be empty
        
        Notes
        -----
        If `bounds` is supplied, `fpaths` will be filtered automatically such
        that any .las files containing no points within the defined bounds
        will be skipped, making it possible to supply a large number of file
        paths for which the spatial locations of the data are not known.
        
        """
        bounds = kwargs.pop('bounds', None)
        allow_empty = kwargs.pop('allow_empty', None)
        if bounds is None and allow_empty is not None:
            raise TypeError('Argument `allow_empty` is meaningless without `bounds`')
        if kwargs:
           raise TypeError('Invalid keyword arguments {}'.format(kwargs.values()))
        
        # Read only relevant files
        if bounds is not None:
            fpaths = filter_fpaths(fpaths, bounds)
        
        # Build pointcloud
        if len(fpaths) > 1:
            pc = cls(_combine_las(*fpaths))
        else:
            try:
                 pc = cls(_get_las_xyz(*fpaths))
            except(TypeError):
                 pc = cls(None)
        
        if bounds is not None:
            pc = pc.crop(bounds, allow_empty=allow_empty)
        
        return pc

    @classmethod
    def from_laspy_File(cls, f):
        """Initialise PointCloud from a laspy File.
        
        Arguments
        ---------
        f: `laspy.file.File` instance
            file object must be open, and will remain so
        
        """
        return cls((f.x, f.y, f.z), header=f.header.copy())

    @classmethod
    def from_txt(cls, *fpaths):
        """Initialise PointCloud from a plaintext file.

        Arguments
        ---------
        fpaths: str
            filepath of an ASCII 3-column (xyz) whitespace-delimited
            .txt (aka .xyz) file
       
        """
        if len(fpaths) > 1:
            raise NotImplementedError
        else:
            return cls(np.loadtxt(*fpaths).T)

    @classmethod
    def from_None(cls):
        """Initialise an empty PointCloud."""
        return cls(None)

    """ Instance methods """
    @property
    def arr(self):
        """Get or set the underlying (x, y, z) array of point coordinates."""
        return self._arr
    
    @arr.setter
    def arr(self, value):
        self._arr = value
    
    @property
    def x(self):
        """The x component of point coordinates."""
        return self._arr[0]

    @property
    def y(self):
        """The y component of point coordinates."""
        return self._arr[1]

    @property
    def z(self):
        """The z component of point coordinates."""
        return self._arr[2]

    @property
    def points(self):
        """Get point coordinates as a structured n*3 array).
        
        Returns
        -------
        structured np.ndarray containing 'x', 'y' and 'z' point coordinates
    
        """
        return self._arr.T.ravel().view(
               dtype=[('x', self.dtype), ('y', self.dtype), ('z', self.dtype)])

    @property
    def bounds(self):
        """Boundary box surrounding PointCloud.
        
        Returns
        -------
        collections.namedtuple (minx, miny, minz, maxx, maxy, maxz)
        
        Raises
        ------
        `simulocloud.exceptions.EmptyPointCloud`
            if there are no points
        """
        x,y,z = self._arr
        try:
            return Bounds(x.min(), y.min(), z.min(),
                          x.max(), y.max(), z.max())
        except ValueError:
            raise simulocloud.exceptions.EmptyPointCloud(
                      "len 0 PointCloud has no Bounds")

    @property
    def header(self):
        """Create a valid header describing pointcloud for output to .las.

        Returns
        -------
        header: laspy.header.Header instance
            header generated from up-to-date point cloud information 
        
        """
        header = _HEADER_DEFAULT.copy()
        bounds = self.bounds
        header.update({'point_return_count': [len(self), 0, 0, 0, 0],
                       'x_offset': round(bounds.minx),
                       'y_offset': round(bounds.miny),
                       'z_offset': round(bounds.minz),
                       'x_min': bounds.minx,
                       'y_min': bounds.miny,
                       'z_min': bounds.minz,
                       'x_max': bounds.maxx,
                       'y_max': bounds.maxy,
                       'z_max': bounds.maxz})

        return laspy.header.Header(**header)
    
    def crop(self, bounds, destructive=False, allow_empty=False):
        """Crop point cloud to (lower-inclusive, upper-exclusive) bounds.
        
        Arguments
        ---------
        bounds: `Bounds`
            (minx, miny, minz, maxx, maxy, maxz) to test point coordinates against
            None results in no cropping at that bound
        destructive: bool (default: False)
            whether to remove cropped values from pointcloud
        allow_empty: bool (default: False)
            whether to allow empty pointclouds to be created or raise
            `simulocloud.exceptions.EmptyPointCloud`
        
        Returns
        -------
        PointCloud instance
            new object containing only points within specified bounds
        
        """
        bounds = Bounds(*bounds)
        oob = points_out_of_bounds(self, bounds)
        # Deal with empty pointclouds
        if oob.all():
            if allow_empty:
                return type(self)(None)
            else:
                raise simulocloud.exceptions.EmptyPointCloud(
                          "No points in crop bounds:\n{}".format(bounds))
         
        cropped = type(self)(self._arr[:, ~oob])
        if destructive:
            self.__init__(self._arr[:, oob])
        return cropped

    def to_txt(self, fpath):
        """Export point cloud coordinates as 3-column (xyz) ASCII file.
    
        Arguments
        ---------
        fpath: str
            path to file to write 
        
        """
        np.savetxt(fpath, self._arr.T)

    def to_las(self, fpath):
        """Export point cloud coordinates to .las file.

        Arguments
        ---------
        fpath: str
            path to file to write
        
        """
        with laspy.file.File(fpath, mode='w', header=self.header,
                             vlrs=[laspy.header.VLR(**_VLR_DEFAULT)]) as f:
            f.x, f.y, f.z = self._arr

    def downsample(self, n):
        """Randomly sample the point cloud.
        
        Arguments
        ---------
        n: int
            number of points in sample
        
        Returns
        -------
        PointCloud
            of len n (or len of this pointcloud if it is <=n)
        
        """
        n = min(n, len(self))
        idx = np.random.choice(len(self), n, replace=False)
        return type(self)(self._arr[:, idx])


    def merge(self, pointclouds):
        """Merge this pointcloud with other instances.
        
        Arguments
        ---------
        pointclouds: sequence of `PointCloud`
        
        """
        pointclouds = [self] + [pc for pc in pointclouds]
        return merge(pointclouds, pctype=type(self))

    def split(self, axis, locs, pctype=None, allow_empty=True):
        """Split this pointcloud at specified locations along axis.
        
        Arguments
        ---------
        axis: str
            point coordinate component ('x', 'y', or 'z') to split along
        locs: iterable of float
            points along `axis` at which to split pointcloud
        pctype: subclass of `PointCloud`
           type of pointclouds to return
        allow_empty: bool (default: True)
            whether to allow empty pointclouds to be created or raise
            `simulocloud.exceptions.EmptyPointCloud`

        Returns
        -------
        pcs: list of `pctype` (PointCloud) instances
            pointclouds with `axis` bounds defined sequentially (low -> high)
            by self.bounds and locs
        """
        # Copy pointcloud
        if pctype is None:
            pctype = type(self)
        pc = pctype(self._arr)
        
        # Sequentially (high -> low) split pointcloud
        none_bounds = Bounds(*(None,)*6)
        pcs = [pc.crop(none_bounds._replace(**{'min'+axis: loc}),
                       destructive=True, allow_empty=allow_empty)
                  for loc in sorted(locs)[::-1]]
        pcs.append(pc)
        
        return pcs[::-1]


class NoneFormatter(string.Formatter):
    """Handle an attempt to apply decimal formatting to `None`.

    `__init__` and `get_value` are from https://stackoverflow.com/a/21664626
    and allow autonumbering.
    """

    def __init__(self):
        super(NoneFormatter, self).__init__()
        self.last_number = 0

    def get_value(self, key, args, kwargs):
        if key == '':
            key = self.last_number
            self.last_number += 1
        return super(NoneFormatter, self).get_value(key, args, kwargs)

    def format_field(self, value, format_spec):
        """Format any `None` value sans specification (i.e. default format)."""
        if value is None:
            return format(value)
        else:
            return super(NoneFormatter, self).format_field(value, format_spec)
            if value is None:
                return format(value)
            else: raise e


class Bounds(collections.namedtuple('Bounds', ['minx', 'miny', 'minz',
                                   'maxx', 'maxy', 'maxz'])):
    """(minx, miny, minz, maxx, maxy, maxz) box bounding a pointcloud."""
    __slots__ = ()
    _format = '{:.3g}'
    
    def __str__(self):
        """Truncate printed values as specified by class attribute `_format`."""
        template = ('Bounds: minx={f}, miny={f}, minz={f}\n        '
                    'maxx={f}, maxy={f}, maxz={f}'.format(f=self._format))
        # Formatter must be recreated each time to reset value counter
        return NoneFormatter().format(template, *self)

class InfBounds(Bounds):
    """`Bounds` with `None`s coerced to `inf`s."""
    __slots__ = ()

    def __new__(cls, minx, miny, minz, maxx, maxy, maxz):
        """Create new instance of Bounds(minx, miny, minz, maxx, maxy, maxz)
        
        Args
        ----
        minx, miny, minz, maxx, maxy, maxz: numeric or None
            minimum or maximum bounds in each axis
            None will be coerced to -numpy.inf (mins) or numpy.inf (maxes)
        
        """
        # Coerce bounds to floats, and nones to infs
        kwargs = locals()
        for b, inf in zip(('min', 'max'),
                          (-np.inf, np.inf)):
            for axis in 'xyz':
                bound = b + axis
                value = kwargs[bound]
                kwargs[bound] = inf if value is None else float(value)
        
        kwargs.pop('cls') # must be passed positionally
        return super(cls, cls).__new__(cls, **kwargs)

def filter_fpaths(fpaths, bounds):
    """Keep only .las files whose pointclouds intersect with `bounds`.
    
    Arguments
    ---------
    fpaths: iterable of str
        filepaths of .las files
    bounds: `Bounds` or simiiliar
        (minx, miny, minz, maxx, maxy, maxz) bounds of tile
        `None` values are inclusive (i.e. no filtering for that bound)
    
    Returns
    -------
    list of str
        subset of `fpaths` whose pointclouds overlap with bounds
    
    """
    bounds = InfBounds(*bounds)
    return [fpath for fpath in fpaths
            if _intersects_3D(bounds, _get_las_bounds(fpath))]

def _combine_las(*fpaths):
    """Efficiently combine las files to a single [xs, ys, zs] array."""
    sizes = {fpath: _get_las_npoints(fpath) for fpath in fpaths}
    npoints = sum(sizes.values())
    arr = np.empty((3, npoints), dtype = _DTYPE) # initialise array
    
    # Fill array piece by piece
    i = 0 # start point
    for fpath, size in sizes.iteritems():
        j = i + size # end point
        arr[:,i:j] = _get_las_xyz(fpath)
        i = j
    return arr

def _get_las_npoints(fpath):
    """Return the number of points in a .las file.
    
    Note: npoints is read from the file's header, which is not guuaranteed
          to be at all accurate. This may be a source of error.
    """
    with laspy.file.File(fpath) as f:
        return f.header.count

def _get_las_xyz(fpath):
    """Return [x, y, z] list of coordinate arrays from .las file."""
    with laspy.file.File(fpath) as f:
        return [f.x, f.y, f.z]

def _get_las_bounds(fpath):
    """Return the bounds of file at fpath."""
    with laspy.file.File(fpath) as f:
        return Bounds(*(f.header.min + f.header.max))

def _intersects_1D(A, B):
    """True if (min, max) tuples intersect."""
    return False if (B[1] <= A[0]) or (B[0] >= A[1]) else True

def _intersects_3D(A, B):
    """True if bounds A and B intersect."""
    return all([_intersects_1D((A[i], A[i+3]), (B[i], B[i+3]))
                for i in range(3)])

def _iter_points_out_of_bounds(pc, bounds):
    """Iteratively determine point coordinates outside of bounds.

    Arguments
    ---------
    pc: `PointCloud` instance
    bounds: `Bounds`
        (minx, miny, minz, maxx, maxy, maxz) to test point coordinates against
    
    Returns
    -------
    generator (len 6)
        yields, for each bound of lower, upper of x, y, z, not equal to `None`,
        a boolean numpy.ndarray describing whether each point falls outside of
        that bound in that axis
    
    Notes
    -----
    Comparisons are python-like, i.e.:
        x < minx
        x >= maxx
    Comparisons to `None` are skipped (generator will be empty if all bounds
    are `None`)
    """
    for i, axis_coords in enumerate(pc.arr):
        for compare, bound in zip((np.less, np.greater_equal),
                                  (bounds[i], bounds[i+3])):
            if bound is not None:
                yield compare(axis_coords, bound)

def points_out_of_bounds(pc, bounds):
    """ Determine whether each point in pc is out of bounds
    
    Arguments
    ---------
    pc: `PointCloud` instance
    bounds: `Bounds`
        (minx, miny, minz, maxx, maxy, maxz) to test point coordinates against
    
    Returns
    -------
    `numpy.ndarray` (shape=(len(pc),))
        bools specifying whether any of the (x, y, z) component of point
        coordinates in `pc` are outside of the specified `bounds`
    
    """
    oob = np.zeros(len(pc), dtype=bool)
    for comparison in _iter_points_out_of_bounds(pc, bounds):
        oob = np.logical_or(comparison, oob)
    return oob

def _inside_bounds(A, B):
    """Return True if bounds `A` fits entirely inside bounds `B`"""
    for axis in 'xyz':
        minA, maxA = axis_bounds(A, axis)
        minB, maxB = axis_bounds(B, axis)
        if (minA <= minB) or (maxA >= maxB):
            return False

    return True

def axis_bounds(pc, axis):
    """Return (min, max) of `axis` in bounds of `PointCloud` (or `Bounds`) `pc`."""
    try:
        bounds = pc.bounds
    except AttributeError:
        bounds = pc
    
    return tuple([getattr(bounds, b + axis) for b in ('min', 'max')])

def merge_bounds(ibounds):
    """Find overall bounds of pcs (or bounds).
    
    Arguments
    ---------
    ibounds: iterable of `Bounds` (or similiar)
         None values will be treated as appropriate inf
    
    Returns
    -------
    `Bounds`
        describing total area covered by args
    
    """
    # Coerce Nones to Infs
    all_bounds = [InfBounds(*bounds) for bounds in ibounds]
    
    # Extract mins/maxs of axes
    all_bounds = np.array(all_bounds)
    return Bounds(all_bounds[:,0].min(), all_bounds[:,1].min(), all_bounds[:,2].min(),
                  all_bounds[:,3].max(), all_bounds[:,4].max(), all_bounds[:,5].max())

"""PointCloud manipulation"""

def merge(pointclouds, pctype=PointCloud):
    """Return `pointclouds` merged to a single instance of `pctype`.
    
    Arguments
    ---------
    pointclouds: sequence of `PointCloud` (or subclass)
    pctype: type of pointcloud to return (default=`PointCloud`)
    
    Returns
    -------
    instance of `pctype`
        contains all points in `pointclouds`
    
    """
    sizes = [len(pc) for pc in pointclouds]
    arr = np.empty((3, sum(sizes)), dtype=_DTYPE)
    
    # Build up array from pcs
    i = 0
    for pc, size in zip(pointclouds, sizes):
        j = i + size
        arr[:,i:j] = pc.arr
        i = j
    return pctype(arr)
