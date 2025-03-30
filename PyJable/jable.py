#
"""
The `JyFrame` can be treated like tabular data, indexed by a row integer and column string. You access it much like a 2 dimensional `numpy.ndarray` but always with 2 dimensions. There is even an optional field for storing column classes. No parts of the JyFrame base enforce or set any of these, and they are left purely for extensions.

  There are five parts to the JyFrame:

    #. `shift`: A regular dictionary mapping string column names to lists of literal values
    #. `shiftIndex`: A set of values which the user can mostly ignore. If a column from `shift` is present as a key in `shiftIndex` then for `col: str`, the values in the list of `shift[col]` will be integers, referring to the object in the corresponding index of `shiftIndex[col]`. So if `shift["name"][3] = 1` and `shiftIndex["name"] = ["Tom","Jerry"]`, then the real value of `shift["name"][3] = shiftIndex["name"][1] = "Jerry"`.
    #. `fixed`: A "column" which has the same value in every row. This allows us to list the value only once. Beware updating this, as it will change the value for every row. There are two ways to consider `fixed`:
        
        #. A space saver, where we simply have the same value for every row. In this case, you can ignore that it's different from any other columns or values
        
        #. A set of variables associated with the entire table. For example, you might have a relative `"path"` column, which is relative to a fixed `"root"`. If you know this is the case, you should treat it specially with your code, and keep track using the ``JyFrame.fixed_keys()`` method.
        
    #. `keyTypes`: dictionary mapping columns to a type as a python type, or a string. The base JyFrame class makes no checks or enforcement of this; it is only to keep track of columns for the user. As a result, the user can provide `customTypes: dict[ str, type ]` argument to ``JyFrame()``. Otherwise, strings as classes will be left as strings in the `keyTypes` dictionary. Upon serialization to a dict, such as for saving, it will turn into `{ col: str(_type) for col, _type in keyTypes.values() }`.
    
    #. `meta`: An arbitrary dictionary. The base JyFrame code does not write or read this, but it will preserve it when serializing as well as possible. Store whatever information you want here for subclasses or business logic, but try to make it serializable.

Iterating over a JyFrame gives each row as a dictionary. see ``PyJable.jable.__getitem__()`` for about accessing one or many items in the table. See ``PyJable.jable.JyFilter()`` for selecting and filtering rows.
"""

import json

from collections.abc import Sequence
from typing import Callable, Literal, Self
from sys import path

# Dictionary representation of the data in a JyFrame
JyFrameDict: type = dict[{
    "_fixed": dict[ str, any ],
    "_shift": dict[ str, list ],
    "_shiftIndex": dict[ str, list ],
    "_keyTypes": dict[ str, str | type ],
    "_meta": dict[ str, any ]
}]

# SString representation of the most common datatypes
# Does no enforcement or conversion; it can be set freely and can be any string
# or type. It's for the user's convenience
_BASE_TYPES: list[ type ] = [
    str, int, float,
    list, dict
]

_TYPES_DICT: dict[ str, type ] = {
    str( _type ): _type for _type in _BASE_TYPES
}

# JyFilter: A way to check if rows match some criterion, either by equality with every value in a dictionary, or evaluating as true with a lambda taking the row dictionary as an input
JyFilter: type = dict[ str, any ] | Callable[ dict[ str, any ], bool ]

def row_does_matchJyFilter(
    row: dict[ str, any ],
    jyFilter: JyFilter
    ) -> bool:
    """
        The way to check if a row dictionary matches a jyFilter
        
        For dictionaries, check equality on every key
        
        For Callables, just run the Callable on the row
    """
    if isinstance( jyFilter, dict ):
        return all(
            row[ key ] == jyFilter[ key ] for key in jyFilter
        )
    #
    
    if isinstance( jyFilter, Callable ):
        return jyFilter( row )
    #
    
    raise Exception("Unrecognized jyFilter={}".format(jyFilter))
#/def row_does_matchJyFilter

class JyFrame():
    """
        Stores column data as a combination of three parts:
        
        :param dict[ str, any ] fixed: Columns with the same name for value in every row. You can change its value but that will essentially change it for every row; try to only change it in code that knows it's a fixed key, and sets and gets it with the fixed methods (`.keys_fixed()`, `.get_fixed(...)`)
        :param dict[ str, list ] shift: Where we have a listed literal item as a value, typically a string, float or int, sometimes lists of them, sometimes dictionaries or any other objects
        :param dict[ str list ] shiftIndex: Sometimes, shift columns will have the same value repeated many times. If its column name is in shift index, then the values in shift are integers, referring to the index in shiftIndex of the same column. I.e., if we have `shift["fur_color"] = [1,0,2]` and `shiftIndex["fur_color"] = ["green","orange","purple","red"]`, then the `"fur_color"`s are really `["orange","green","purple"]`
        :param dict[ str, str | type ] keyTypes: Optional types to set for any columns. No enforcement is done by the JyFrame itself, whether inserting or retriving. It is for your own use. These will be serialized as strings using `str` so add the appropriate functions for custom classes to serialize it as you want, and convert into a class upon reading. Includes support for basic python types
        :param dict[ str, any ] meta: Another arbitrary dictionary to hold domain specific data, in the jyFrame as `._meta`. No methods write or use this, so edit and read at will or subclass.
        :param dict[ str, type ] customTypes: A reference to use for deserializing string types from `keyTypes`. Gets checked before builtin types
        
        see ``.__getitem__`` for acessing values
    """
    def __init__(
        self: Self,
        fixed: dict[ str, any ] = {},
        shift: dict[ str, list] = {},
        shiftIndex: dict[ str, list ] = {},
        keyTypes: dict[ str, type ] = {},
        meta: dict[ str, any ] = {},
        customTypes: dict[ str, type ] = {}
        ):
        
        self._fixed = fixed
        self._shift = shift
        self._shiftIndex = shiftIndex
        self._meta = meta
        self._customTypes = customTypes
        
        # Handle key types by using ._customTypes and _TYPES_DICT
        self._keyTypes = {}
        for col, _type in keyTypes.items():
            if isinstance( _type, str ):
                # Check custom types first
                if _type in self._customTypes:
                    self._keyTypes[ col ] = self._customTypes[ _type ]
                #
                # Not custom, check builtins
                elif _type in _TYPES_DICT:
                    self._keyTypes[ col ] = _TYPES_DICT[ _type ]
                #
                # Cannot find, leave as string
                else:
                    self._keyTypes[ col ] = _type
                #/if _type in self._customTypes
            #/if isinstance( _type, str )
            elif isinstance( _type, type ):
                # It's a type
                self._keyTypes[ col ] = _type
            #
            else:
                raise Exception("Unrecognized col, _type={},{}".format(col,_type))
            #/switch type( _type )
        #/for col, _type in keyTypes
        
        assert all( key in self._shift for key in self._shiftIndex )
        
        if self._shift != {}:
            self._len = 0
            for key in self._shift:
                if self._len == 0:
                    self._len = len( self._shift[ key ] )
                #
                else:
                    assert len( self._shift[key] ) == self._len
                #/if self._len == 0/else
            #/for key in self._shift
        #/if self._shift != {}
        else:
            self._len = 0
        #/if self._shift != {}/elif self._fixed != {}/else

        self.shape = (self._len, len( self._fixed ) + len( self._shift ))
    #/def __init__
    
    # -- Info
    
    def _list_fromSlice(
        self: Self,
        rows: slice
    ) -> list[ int ]:
        """
            Turns common slice notation into an appropriate list of ints
        """
        return [i for i in range( *rows.indices(self._len) ) ]
    #/def _list_fromSlice
    
    def __len__( self: Self ) -> int:
        return self._len
    #
    
    def keys( self: Self ) -> list[ str ]:
        """
            Gets the equivalent of all column names of the jyFrame, including fixed and nonfixed
        """
        return list( self._fixed.keys() ) + list( self._shift.keys() )
    #
    
    def keys_fixed( self: Self ) -> list[ str ]:
        """
            Returns the keys for the fixed dictionary. This is so we don't have to have `._fixed` used externally
        """
        return list( self._fixed.keys() )
    #
    
    def keys_shift( self: Self ) -> list[ str ]:
        """
            All named keys in `._shift`, which includes `._shiftIndex`
        """
        return list( self._shift.keys() )
    #
    
    def makeColumn_shift(
        self: Self,
        col: str
        ) -> None:
        """
            Converts a column to a shift column
        """
        if col in self._shift:
            return
        #
        if col in self._fixed:
            self._shift[ col ] = [ self._fixed[ col ] ]*len( self )
            del self._fixed[ col ]
            return
        #
        raise Exception("Missing from keys col={}".format(col))
    #/def makeColumn_shift
    
    # -- Getting and Iterating
    
    def __iter__( self: Self ) -> "JyFrameIterator":
        """
            Goes through by row giving each row as a dictionary
        """
        return JyFrameIterator( self )
    #
    
    def _item_by_rowCol(
        self: Self,
        row: int,
        col: str
        ) -> any:
        if col in self._fixed:
            return self._fixed[ col ]
        #
        elif col in self._shiftIndex:
            return self._shiftIndex[ col ][ self._shift[col][row] ]
        #
        elif col in self._shift:
            return self._shift[ col ][ row ]
        #
        else:
            raise Exception("Bad col={}".format( col ))
        #
    #/def _item_by_rowCol
    
    def _select_rows_andColumns(
        self: Self,
        rows: list[ int ] = [],
        columns: list[ str ] = []
        ) -> Self:
        """
            :param list[ int ] rows: Which rows to get. Default is all.
            :param list[ str ] col: Which columns to get. Default is all.
            
            Returns a new table copy of the given rows and columns. Used primarily by ``.__getitem__()``
        """
        from copy import deepcopy
        
        if rows == []:
            rows = [ i for i in range( len(self) ) ]
        #
        
        if columns == []:
            columns = self.keys()
        #
        
        # Initialize new table
        fixed = {
            key: val for key, val in self._fixed.items() if key in columns
        }
        
        shift = {
            col: [
                self._shift[ col ][ i ] for i in rows
            ] for col in columns if col in self._shift
        }
        
        # Need all shiftIndex values
        shiftIndex = {
            col: self._shiftIndex[ col ] for col in columns if col in self._shiftIndex
        }
        return JyFrame(
            fixed = fixed,
            shift = shift,
            shiftIndex = shiftIndex,
            keyTypes = deepcopy( self._keyTypes ),
            meta = deepcopy( self._meta ),
            customTypes = deepcopy( self._customTypes )
        )
    #/def _select_rows_andColumns
    
    def __getitem__(
        self: Self,
        index: int | str | tuple[
            int | slice | Sequence[ int ],
            str | Sequence[ str ]
        ] | slice | Sequence[
            int
        ] | Sequence[
            str
        ]
        ) -> any:
        """
            :param int|str|tuple[int | slice | Sequence[ int ], str | Sequence[ str ] ]|slice|Sequence[ int ]|Sequence[ str ] index: Table accessor
        
            `jyFrame[ row: int, col: str ] -> any` A single item at a location

            `jyFrame[ col: str ] -> list` The entire column of values

            `jyFrame[ row: int ] -> dict[ str, any ]` One row as a dictionary with all keys

            `jyFrame[ rows: Sequence[ int ] | slice ] -> JyFrame` Subset of rows, all columns

            `jyFrame[ columns: Sequence[ str ] ] -> JyFrame` Subset of columns, all rows

            `jyFrame[ row: int, columns: Sequence[ str ] ] -> dict[ str, any ]` One row as a dictionary with subset of columns

            `jyFrame[ rows: Sequence[ int ] | slice, col: str ] -> list`: One column, subset of rows as a list of those items. (If you want to keep some index, then have that index as another column)

            `jyFrame[ rows: Sequence[ int ] | slice, columns: Sequence[ str ] ] -> jyFrame` Subset of both columns and columns
        """
        # -- Double value, like `jyFrame[ row, col ]`
        if isinstance( index, tuple ) and len( index ) == 2:
            row = index[0]
            column = index[1]
            if isinstance( row, int ):
                row = [ row ]
            #
            elif isinstance( row, slice ):
                # Row is a slice
                # Convert row to indices
                row = self._list_fromSlice(
                    row
                )
            elif isinstance( row, Sequence ):
                # List of ints, most likely
                ...
            #
            else:
                raise Exception("bad row={}".format( row ) )
            #
            
            if isinstance( column, str ):
                if len( row ) == 1:
                    return self._item_by_rowCol( row[0], column )
                #
                elif len( row ) > 1:
                    # Return list of items
                    values: list[ any ] = [
                        self._shift[ column ][ i ] for i in row
                    ]
                    if column in self._shiftIndex:
                        for i in range( len( values ) ):
                            if values[ i ] is not None:
                                values[ i ] = self._shiftIndex[ column ][ values[i] ]
                            #/if values[ i ] is not None
                        #/for i in range( len( values ) )
                    #/if column in self._shiftIndex
                    return values
                #/if len( row ) == 0 /else
                else:
                    raise Exception("Bad row={}".format(row))
                #/switch len( row )
            #
            elif isinstance( column, Sequence ):
                _self_keys: list[ str ] = self.keys()
                assert all( col in _self_keys for col in column )
                if len( row ) == 1:
                    item = self._fixed | {
                        col: self._shift[ col ][ row[0] ] for col in column if col in self._shift
                    }
                    for col in item:
                        if item[ col ] is not None and col in self._shiftIndex:
                            item[ col ] == self._shiftIndex[ col ][
                                item[ col ]
                            ]
                        #/if item[ col ] is not None and col in self._shiftIndex
                    #/for col in item
                    return { col: val for col, val in item.items() if col in column }
                elif len( row ) > 1:
                    return self._select_rows_andColumns(
                        rows = row,
                        columns = column
                    )
                #
                else:
                    raise Exception("# Bad row={}".format(row))
                #/switch len( row )
            #
            else:
                # TODO: return new jyFrame if column is a sequence
                raise Exception("Bad column={}".format( column ))
            #/switch { type index }
        #/if isinstance( index, tuple ) and len( index ) == 2
        # -- "Single" Items
        #   Can be one or multiple rows OR columns, but not both
        elif isinstance( index, int ):
            item = self._fixed | {
                key: self._shift[ key ][ index ] for key in self._shift
            }
            for key in item:
                # Update from shiftIndex for values that aren't None
                if item[ key ] is not None and key in self._shiftIndex:
                    item[ key ] = self._shiftIndex[ key ][ item[key] ]
                #/item[ key ] is not None and key in self._shiftIndex
            #/for key in item
            return item
        elif isinstance( index, str ):
            # Name a column
            if index in self._shiftIndex:
                return [
                    self._shiftIndex[ index ][ val ] for val in self._shift[ index ]
                ]
            #
            elif index in self._shift:
                return self._shift[ index ]
            #
            else:
                raise Exception("Bad column={}".format(index))
            #
        #
        elif isinstance( index, Sequence ):
            if all( isinstance( val, str ) for val in index ):
                # ["col0","col1",...]
                return self._select_rows_andColumns(
                    columns = index
                )
            #
            if all( isinstance( val, int ) for val in index ):
                # [0,1,2,...]
                return self._select_rows_andColumns(
                    rows = index
                )
            #
        #
        elif isinstance( index, slice ):
            # Rows
            return self._select_rows_andColumns(
                rows = self._list_fromSlice(
                    index
                )
            )
        else:
            raise Exception("Bad index={}".format(index))
        #/switch { type( index ) }
    #/def __getitem__
    
    def get_fixed( self: Self, key: str, default: any = None ) -> any:
        """
            :param str key: Value to get from `._fixed`
            :param any default: Value to get if key not present in `._fixed`, if not `None`
            
            Gets a value known to be associated with a fixed key. This means we don't have to access any shift lists
        """
        if default is None or key in self._fixed:
            return self._fixed[ key ]
        #
        # Don't have key present, and we have some default
        return default
    #/def get_fixed
    
    def get_fixed_withDefaultDict(
            self: Self, default: dict[ str, any ]
        ) -> dict[ str, any ]:
        return {
            key: self.get_fixed( key, val ) for key,val in default.items()
        }
        """
            :param dict[ str, any ] default: Values to put in result if the corresponding keys are not present
            
            Allows programs to give a default value for keys which are not in `_fixed`, and otherwise gives the `_fixed` values. This saves the headache of repeatedly checking `.keys_fixed()`
        """
    #/def get_fixed_withDefaultDict
    
    def as_dict( self: Self ) -> JyFrameDict:
        """
            The dictionary, ready to be saved to the disk as json
            
            Saves types as their stringified version (if the types are serializable)
        """
        _keyTypes: dict[ str, str ] = {
            col: str( _type ) for col, _type in self._keyTypes.items()
        }
        return {
            "_fixed": self._fixed,
            "_shift": self._shift,
            "_shiftIndex": self._shiftIndex,
            "_keyTypes": _keyTypes,
            "_meta": self._meta
        }
    #/def as_dict
    
    def __str__( self ):
        """
            Self as a nested dictionary
        """
        return str( self.as_dict() )
    #/def __str__
    
    # -- Indexing
    
    def does_matchIndex(
        self: Self,
        jyFilter: JyFilter,
        index: int
        ) -> bool:
        """
            Check to see if a row matches a given jyFilter
        """
        return row_does_matchJyFilter(
            row = self[ index ],
            jyFilter = jyFilter
        )
    #/def does_matchIndex
    
    def any_matchingIndices(
        self: Self,
        jyFilter: JyFilter
        ) -> bool:
        """
            Says if at least one row matches jyFilter
        """
        if isinstance( jyFilter, dict ):
            fixed_keys = [ key for key in jyFilter if key in self._fixed ]
            if not all( self._fixed[key] == jyFilter[key] for key in fixed_keys ):
                return False
            #
        #
        
        return any(
            self.does_matchIndex(
                jyFilter = jyFilter,
                index = index
            ) for index in range( len( self ) )
        )
        return False
    #/def any_matchingIndices
    
    def get_matchingIndices(
        self: Self,
        jyFilter: JyFilter
        ) -> list[ int ]:
        """
            Get a list of indices which match jyFilter
        """
        if isinstance( jyFilter, dict ):
            fixed_keys = [ key for key in jyFilter if key in self._fixed ]
            if not all( self._fixed[key] == jyFilter[key] for key in fixed_keys ):
                return []
            #
        #
        
        return [
            index for index in range( len( self ) ) if self.does_matchIndex(
                jyFilter = jyFilter,
                index = index
            )
        ]
    #/def get_matchingIndices
    
    
    # -- Modification: Setting new Values
    
    def _set_index_withDict(
        self: Self,
        index: int,
        row: dict[ str, any ] | Sequence
        ) -> None:
        """
            Updates a specific rows with a given set of values
            
            If we update with a Sequence, then it must correspond to self.keys()
        """
        # Wrangle row into a dict if necessary
        if isinstance( row, dict ):
            ...
        #
        elif isinstance( row, Sequence ):
            # Row must match self.keys()
            assert len( row ) == self.shape[1]
            _keys = self.keys()
            
            row = {
                _keys[j]: row[j] for j in range( self.shape[1] )
            }
        #
        else:
            raise Exception("Bad row={}".format( row ))
        #/switch type( row )
        
        updated_shift: bool = False
    
        for key, val in row.items():
            if key in self._fixed:
                if self._fixed[ key ] is None:
                    assert val is None
                #
                else:
                    # 2025-02-21: We now support updating the fixed value
                    # It's "fixed" in the sense that it's the same for every row
                    self._fixed[ key ] = val
                #/if self._fixed[ key ] is None/else
            else:
                if not key in self._shift:
                    print(
                        "Bad key={}, expected to find in {}".format(
                            key, list( self._shift.keys() )
                        )
                    )
                    raise Exception("Bad key")
                #
                if val is None:
                    self._shift[ key ][ index ] = val
                #
                elif key in self._shiftIndex:
                    newvalue_index: int
                    if val in self._shiftIndex[ key ]:
                        newvalue_index = self._shiftIndex[ key ].index( val )
                    #
                    else:
                        newvalue_index = len( self._shiftIndex[ key ] )
                        self._shiftIndex[ key ].append( val )
                    #
                    self._shift[ key ][ index ] = newvalue_index
                #
                else:
                    self._shift[ key ][ index ] = val
                #/switch val/key
                updated_shift = True
            #/if key in self._fixed/else
        #/for key in row
        if index == len( self ) and updated_shift:
            self._len += 1
            self.shape = ( self._len, self.shape[1] )
        elif index < len( self ):
            ...
        else:
            raise Exception("Bad index={} for updating len={}".format( index, len( self ) ))
        #/switch index
        return
    #/def _set_index_withDict
    
    def _set_fixed(
        self: Self,
        col: str,
        newvalue: any
        ) -> None:
        self._fixed[ col ] = newvalue
        return
    #/def _set_fixed
    
    def _set_column_withList( self: Self, col: str, newList: list[ any ] ) -> None:
        assert len( self ) == len( newList )
        for i in range( len( self ) ):
            self._set_index_withDict(
                index = i,
                row = {
                    col: newList[ i ]
                }
            )
        #/for i in range( len( self ) )
        return
    #/def _set_column_withList
    
    def _set_column_withDict(
        self: Self,
        col: str,
        newDict: dict[ int, any ]
        ) -> None:
        for i, newvalue in newDict.items():
            self._set_index_withDict(
                index = i,
                row = { col: newvalue }
            )
        #/for i, newvalue in newDict.items()
        return
    #/def _set_column_withDict
    
    def _setItem_withDuple(
        self: Self,
        newvalue: any,
        rows: int | slice | Sequence[ int ] = [],
        columns: str | Sequence[ str ] = [],
        ) -> None:
        """
            Called from ``__setitem__()`` when we use bracket setting with two items, like `jyFrame[ row, col ] = newvalue`
            
            Default for rows is all rows, default for columns is all columns
        """
        if rows == []:
            rows = list( range( self.shape[0] ) )
        #
        if columns == []:
            columns = self.keys()
        #
        
        if isinstance( rows, int ) and isinstance( columns, str ):
            # Single cell: `jyFrame[0,"col"] = newvalue`
            self._set_index_withDict( rows, { columns: newvalue } )
            return
        #
        elif isinstance( rows, int ) and isinstance( columns, Sequence ):
            # One row, multiple columns
            if isinstance( newvalue, dict ):
                assert set( newvalue.keys() ) == set( columns )
                self._set_index_withDict(
                    rows, newvalue
                )
                return
            #
            elif isinstance( newvalue, list ):
                assert len( newvalue ) == len( columns )
                self._set_index_withDict(
                    rows,
                    {
                        columns[ j ]: newvalue[ j ] for j in range(
                            len( columns )
                        )
                    }
                )
                return
            #
            else:
                raise Exception("Bad newvalue={}".format( newvalue))
            #/switch type( newvalue )
        #
        elif isinstance( columns, str ) and isinstance( rows, slice | Sequence ):
            # One column, multiple rows
            if isinstance( rows, slice ):
                rows = self._list_fromSlice(
                    rows
                )
            #
            for i in range( len(rows) ):
                self._set_index_withDict(
                    rows[i], { col: newvalue[ i ] }
                )
            #
            return
        #
        elif isinstance( rows, slice | Sequence ) and isinstance( columns, Sequence ):
            # Multiple rows and columns; setting from JyFrame, or a list of lists
            if isinstance( rows, slice ):
                rows = self._list_fromSlice(
                    rows
                )
            #

            assert len( newvalue ) == len( rows )

            for i in range( len( newvalue ) ):
                _val = newvalue[ i ]
                if isinstance( _val, dict ):
                    self._set_index_withDict(
                        rows[ i ],
                        _val
                    )
                #
                elif isinstance( _val, Sequence ):
                    assert len( _val ) == len( columns )
                    self._set_index_withDict(
                        rows[ i ],
                        {
                            columns[j]: _val[j]\
                                for j in range( len( _val ) )
                        }
                    )
                #
                else:
                    raise Exception("Bad _val={}".format( _val ) )
                #/switch type( _val )
            #/for i in range( len( newvalue ) )
            return
        #
        else:
            raise Exception("Bad rows, columns = {},{}".format(rows, columns))
        #/switch type( rows, columns )
        
        raise Exception("Unexpected EoF")
    #/def _setItem_withDuple
    
    # TODO: More cases on index, row
    def __setitem__( self: Self, index: int, newvalue: any ) -> None:
        """
            Used in three primary ways:
            
            `jyFrame[ row: int, col: str ] = newVal: any`: Set single value
            `jyFrame[ row: int ] = newRow: dict`: Set new row
            `jyFrame[ col: str ] = newVal: any`, with `col` in `self._fixed.keys()`: Set a fixed value
            `jyFrame[ col: str ] = newColumn: list[ any ]`: Set entirety of new column
            `jyFrame[ col: str ] = rowsDict: dict[ row: int, newvalue: any ]`: for a dictionary indexed by integers, set those rows for `col` to be the value in the dict
        """
        if isinstance( index, int ):
            # A full row
            if isinstance( newvalue, dict ):
                self._set_index_withDict( index = index, row = newvalue )
                return
            #
            elif isinstance( newvalue, Sequence ):
                _keys = self.keys()
                assert len( newvalue ) == self.shape[1]
                self._set_index_withDict(
                    index = index,
                    row = {
                        _keys[ j ]: newvalue[ j ] for j in range( self.shape[1] )
                    }
                )
                return
            #
            else:
                raise Exception("Bad newvalue={}".format(newvalue))
            #/switch type( newvalue )
        #
        elif isinstance( index, str ):
            if index in self._fixed:
                self._set_fixed(
                    col = index,
                    newvalue = newvalue
                )
                return
            #
            if isinstance( newvalue, list ):
                self._set_column_withList(
                    col = index,
                    newList = newvalue
                )
                return
            #
            if isinstance( newvalue, dict ):
                self._set_column_withDict( col = index, newDict = newvalue )
                return
            #
            raise Exception("Unrecognized index={}, newvalue={}".format( index, newvalue ))
        #
        elif isinstance( index, slice ):
            # Multiple rows
            # newvalue can be a list of dictionaries,
            #  or perhaps a JyFrame. Either way, iterate through
            #  and add to the rows
            rows: list[ int ] = self._list_fromSlice( index )
            self._setItem_withDuple(
                newvalue = newvalue,
                rows = rows
            )
            return
        #
        elif isinstance( index, tuple ) and len( index ) == 2:
            # row(s), col(s)
            self._setItem_withDuple(
                newvalue = newvalue,
                rows = index[0],
                columns = index[1]
            )
            return
        #
        elif isinstance( index, Sequence ):
            # List of rows, or list of strings
            if all(
                isinstance( key, int ) for key in index
            ):
                # List of row indices
                # newvalue better be something like a list of dicts or a JyFrame itself
                self._setItem_withDuple(
                    newvalue = newvalue,
                    rows = index
                )
            #
            elif all(
                isinstance( key, str ) for key in index
            ):
                # List of columns
                self._setItem_withDuple(
                    newvalue = newvalue,
                    columns = index
                )
                return
            #
            else:
                raise Exception("Bad index={}".format( index ))
            #
        #
        else:
            raise Exception(
                "Unrecognized index={}, newvalue={}".format(
                    index, newvalue
                )
            )
        #/switch { class(index), class( newvalue ) }
        raise Exception("Unexpected EoF")
    #/def __setitem__
    
    def insert( self: Self, index: int, newvalue: dict[ str, any ] | list[ any ] ) -> None:
        # Insert `None` at the index for each shift value, then set via __setitem__
        if isinstance( newvalue, dict ):
            ...
        elif isinstance( newvalue, Sequence ):
            assert not isinstance( newValue, Self )
            assert len( newvalue ) == self.shape[1]
            _keys = self.keys()
            newvalue = {
                _keys[j]: newvalue[j]\
                    for j in range( self.shape[1])
            }
        #
        
        for key in self._shift.keys():
            self._shift[ key ].insert( index, None )
        #
        self._len += 1
        self.__setitem__( index = index, newvalue = newvalue )
        return
    #/def insert
    
    def set_where(
        self: Self,
        jyFilter: JyFilter,
        row: dict[ str, any ],
        limit: int | None = None,
        verbose: int = 0
        ) -> None:
        """
            Update every row with the given literal row, if it matches jyFilter
            
            You can set a max number of rows to be updated, speeding things up by ending early
        """
        if limit is None:
            limit = len( self )
        #
        
        if isinstance( jyFilter, dict ):
            # Convert dict to proper selection
            _lambda = lambda _row: all( _row[ key ] == val for key, val in jyFilter.items() )
        #
        else:
            _lambda = jyFilter
        #
        
        update_count: int = 0
        
        for i in range( len( self ) ):
            if _lambda( self[ i ] ):
                if verbose > 2:
                    print("[{}] -> {}".format(i, row))
                #
                for key, val in row.items():
                    self[ i, key ] = val
                #
                update_count += 1
            #
            if update_count >= limit:
                break
            #/if update_count >= limit
        #/for i in range( len( self ) )
        if verbose > 0:
            print("Updated {} rows".format( update_count ) )
        #
        return
    #/def set_where
    
    def append(
        self: Self,
        row: dict[ str, any ],
        strict: bool = True
        ) -> None:
        """
            Add a dictionary as a row dict as the last index
            
            If strict, append row which has keys a subset of the keys of self._shift
            If not strict, append keys from row which are present in self._shift, and None for keys missing from row
        """
        # Make sure fixed keys match
        for key in self._fixed:
            if key in row:
                assert row[key] == self._fixed[key]
            #/if key in row
        #/for key in self._fixed

        if strict:
            assert all( key in self.keys() for key in row )
            
            for key, val in row.items():
                if key in self._fixed:
                    continue
                #
                if val is None:
                    self._shift[ key ].append( val )
                elif key in self._shiftIndex:
                    newvalue_index: int
                    if row[ key ] in self._shiftIndex[ key ]:
                        newvalue_index = self._shiftIndex[ key ].index( row[ key ] )
                    #
                    else:
                        newvalue_index = len( self._shiftIndex[ key ] )
                        self._shiftIndex[ key ].append( row[ key ] )
                    #
                    self._shift[ key ].append( newvalue_index )
                #
                elif key in self._shift:
                    self._shift[ key ].append( row[ key ] )
                #
                # else: guaranteed to be in self.fixed and matching
                #    due to earlier check
                #/switch val/key
            #/for key in row
        #
        else:
            for key in self._shift.keys():
                if key in row:
                    val = row[ key ]
                    if val is None:
                        self._shift[ key ].append( val )
                    #
                    elif key in self._shiftIndex:
                        newvalue_index: int
                        if val in self._shiftIndex[ key ]:
                            newvalue_index = self._shiftIndex[ key ].index( val )
                        #
                        else:
                            newvalue_index = len( self._shiftIndex[ key ] )
                            self._shiftIndex[ key ].append( val )
                        #
                        self._shift[ key ].append( newvalue_index )
                    #
                    else:
                        self._shift[ key ].append( val )
                    #/switch val/key
                #
                else:
                    self._shift[ key ].append( None )
                #/if key in row/else
            #/for key in self._shift.keys()
        #/if strict/else
        self._len += 1
        self.shape = ( self._len, self.shape[1])
        return
    #/def append
    
    def extend(
        self: Self,
        newvalue: Self | Sequence,
        strict: bool = False
        ) -> None:
        """
            Extend with a JyFrame, or something like a list of dictionaries
        """
        print("# appending with strict={}".format( strict ) )
        for val in newvalue:
            self.append(
                val,
                strict = strict
            )
        #
        return
    #/def extend
    
    # -- Removal
    
    def __delitem__( self: Self, index: int ) -> None:
        assert isinstance( index, int )
        assert 0 <= index <= len( self ) - 1
        
        for key in self._shift:
            del self._shift[ key ][ index ]
        #
        self._len -= 1
        self.shape = ( self._len, self.shape[1])
        return
    #/def __delitem__
    
    def _remove_list(
        self: Self,
        index: list[ int ]
        ) -> None:
        # Have to change indices as we remove them
        # Since we go from low to high, subtract 1 from the matching index for each
        #   index previously removed
        remove_count: int = 0
        true_index: int
        for i in index:
            true_index = i - remove_count
            self.__delitem__( true_index )
            remove_count += 1
        #
        return
    #/def _remove_list
    
    def remove(
        self: Self,
        index: int | list[ int ]
        ) -> None:
        """
            Remove a single row, or list of rows. Note that this changes the numeric index of subsequent rows.
        """
        if isinstance( index, list ):
            self._remove_list(
                index
            )
            return
        #
        
        # One index, as an int
        self.__delitem__(
            index
        )
        return
    #/def remove
    
    def remove_where(
        self: Self,
        jyFilter: JyFilter
        ) -> None:
        """
            Remove indices matching jyFilter via `.get_matchingIndices`
        """
        # Have to change indices as we remove them
        # Since we go from low to high, subtract 1 from the matching index for each
        #   index previously removed
        matchingIndices: list[ int ] = self.get_matchingIndices(
            jyFilter
        )
        self.remove(
            matchingIndices
        )
        return
    #/def remove_where
    
    def write_file(
        self: Self,
        fp: str,
        mode: str = 'w',
        encoder: json.JSONEncoder | None = None
        ) -> None:
        """
            Standard method to write to a file as a json, which can be initialized into a jyFrame via `fromDict(...)` after reading
        """
        with open( fp, mode ) as _file:
            json.dump(
                obj = self.as_dict(),
                fp = _file,
                cls = encoder
            )
        #/with open( fp, mode ) as _file
        
        return
    #/def write_file
#/class JyFrame

class JyFrameIterator():
    def __init__(
        self: Self,
        jyFrame: JyFrame
    ):
        self._index = 0
        self._jyFrame = jyFrame
    #/def __init__
    
    def __next__( self: Self ) -> dict:
        if self._index > len( self._jyFrame ) - 1:
            raise StopIteration
        #
        else:
            self._index += 1
            return self._jyFrame._fixed | {
                key: self._jyFrame._shiftIndex[ key ][ val[ self._index-1 ] ] \
                    for key, val in self._jyFrame._shift.items() if key in self._jyFrame._shiftIndex
            } | {
                key: val[ self._index-1 ] \
                    for key, val in self._jyFrame._shift.items() if key not in self._jyFrame._shiftIndex
            }
        #/if self._index > len( self._jyFrame ) - 1/else
    #/def __next__
#/class JyFrameIterator

# -- Initializers

def fromDict(
    jyFrameDict: JyFrameDict
    ) -> JyFrame:
    """
        Converts the raw json to JyFrame, without adding any structure
    """
    return JyFrame(
        fixed = jyFrameDict["_fixed"],
        shift = jyFrameDict["_shift"],
        shiftIndex = jyFrameDict["_shiftIndex"],
        keyTypes = jyFrameDict["_keyTypes"],
        meta = jyFrameDict["_meta"]
    )
#/def fromDict

def fromShiftIndexHeader(
    fixed: dict[ str, any ] | list[ str ] = {},
    shift: dict[ str, list ] = {},
    shiftIndexHeader: list[ str ] = [],
    keyTypes: dict[ str, type ] = {},
    meta: any = {}
    ) -> JyFrame:
    from copy import deepcopy
    shiftIndex = {}
    
    # Figure out the true header by taking the union
    shiftHeader: list[ str ] = list(
        set(
            shiftIndexHeader + list( shift.keys() )
        )
    )
    
    if isinstance( fixed, list ):
        # Convert list of strings to a map to `None`
        fixed = {
            key: None for key in fixed
        }
    #
    
    jyFrame: JyFrame = JyFrame(
        fixed = fixed,
        shiftIndex = {
            _key: [] for _key in shiftIndexHeader
        },
        shift = {
            _key: [] for _key in shiftHeader
        },
        keyTypes = keyTypes,
        meta = meta
    )
    
    if shift == {}:
        return jyFrame
    #
    
    # Add items
    _len: int = len(
        next(
            _val for _val in shift.values()
        )
    )
    
    for i in range( _len ):
        jyFrame.append(
            {
                _key: _val[ i ] for _key, _val in shift.items()
            }
        )
    #
    
    return jyFrame
#/def fromShiftIndexHeader

def fromHeaders(
    fixed: dict[ str, any ] | list[ str ] = {},
    shiftHeader: list[ str ] = [],
    shiftIndexHeader: list[ str ] = [],
    keyTypes: dict[ str, type ] = {},
    meta: any = {}
    ) -> JyFrame:
    """
        Initializes a jyFrame with the given headers, but no data (with the possible exception of `fixed`)
    """
    if isinstance( fixed, list ):
        # Convert list of strings to a map to `None`
        fixed = {
            key: None for key in fixed
        }
    #
    
    shiftHeaderAll = shiftIndexHeader + [
        col for col in shiftHeader if col not in shiftIndexHeader
    ]
    
    return JyFrame(
        fixed = fixed,
        shift = { col: [] for col in shiftHeaderAll },
        shiftIndex = { col: [] for col in shiftIndexHeader },
        keyTypes = keyTypes,
        meta = meta
    )
#/def fromHeaders

def fromDict_shift(
    data: dict[ str, list ],
    validate: bool = True
    ) -> JyFrame:
    """
        :param dict[ str, list ] data: Reads a dictionary of lists, with keys as column names and values as those columns. Result is making the shift dict from `data`
        :param bool validate: If `True` check each value of `data` is a list of the same length
    """
    # Check for correct data lengths
    if validate:
        assert isinstance( data, dict )
        data_len: int | None = None
        for val in data.values():
            assert isinstance( val, list )
            if data_len is None:
                data_len = len( val )
            #
            else:
                assert len( val ) == data_len
            #/if data_len is None
        #/for val in data.values()
    #/if validate
    
    return JyFrame( shift = data )
#/def fromDict_shift

def likeJyFrame(
    jyFrame: JyFrame
    ) -> JyFrame:
    """
        :param JyFrame jyFrame: Frame to intialize like, copying fixed, the shift header, the shift index header, keyTypes, and meta
        
        
        Gives a blank jyFrame with copied headers
    """
    return fromHeaders(
        fixed = jyFrame._fixed,
        shiftHeader = [
            key for key in jyFrame._shift.keys()
        ],
        shiftIndexHeader = [
            key for key in jyFrame._shiftIndex.keys()
        ],
        keyTypes = jyFrame._keyTypes,
        meta = jyFrame._meta
    )
#/def likeJyFrame

def fromFile(
    fp: str,
    decoder: json.JSONDecoder | None = None,
    strict: bool = False,
    update: bool = False
    ) -> JyFrame:
    """
        :param str fp: File path to read
        :param json.JSONDecoder|None decoder: Optional custom decoder
        :param bool strict: If `True` require exact correct formatting, will raise if not
        :param bool update: If `True` and `strict = False` it will update the file on the disk with missing fields
        
        Reads directly as a jyFrame on the disk in json form
    """
    with open( fp, 'r' ) as _file:
        data: JyFrameDict = json.load( fp = _file, cls = decoder )
    #
    
    data_all: JyFrameDict
    
    # Check is has all required fields when `strict` mode
    _REQUIRED_KEYS = ["_fixed","_shift","_shiftIndex","_keyTypes'", "_meta"]
    if strict:
        if any( key not in data for key in _REQUIRED_KEYS ):
            raise Exception(
                "Unrecognized file keys={}".format(
                    data.keys()
                )
            )
        #/if any( key not in data for key in _REQUIRED_KEYS )
        if any( key not in _REQUIRED_KEYS for key in data ):
            raise Exception(
                "Unrecognized file keys={}".format(
                    data.keys()
                )
            )
        #
        
        data_all = {
            key: {} for key in _REQUIRED_KEYS
        } | data
    #
    else:
        data_all = {
            key: {} for key in _REQUIRED_KEYS
        } | data
    #/if strict/else
    
    jFrame: JyFrame = fromDict( data_all )
    
    # Write file if it's missing a section and
    if update and any( key not in data for key in _REQUIRED_KEYS ):
        jFrame.write_file( file = file )
    #
    
    return jFrame
#/def fromFile

def from_file(
    fp: str,
    decoder: json.JSONDecoder | None = None
    ) -> JyFrame:
    """
        :param str fp: File path to read
        :param json.JSONDecoder|None decoder: Optional customer decoder
        
        Directly reads from a regular json on the disc. Synonym to `fromFile()`
    """
    return fromFile( fp = fp, decoder = decoder )
#/def fromFile

def read_file(
    fp: str,
    decoder: json.JSONDecoder | None = None
    ) -> JyFrame:
    """
        :param str fp: File path to read
        :param json.JSONDecoder|None decoder: Optional customer decoder
        
        Directly reads from a regular json on the disc. Synonym to `fromFile()`
    """
    return fromFile( fp = fp, decoder = decoder )
#/def read_file

def fromFile_shift(
    fp: str,
    decoder: json.JSONDecoder | None = None
    ) -> JyFrame:
    """
        Reads the jyFrame as the shift data only, with no fixed and no meta
        
        This is a niche use, for when a jyFrame has been stored as a dictionary of lists at the top level
    """
    with open( fp, 'r' ) as _file:
        data: dict = json.load( fp = _file, cls = decoder )
    #
    
    return fromDict_shift( data )
#/def fromFile_shift

def read_csv(
    fp: str
    ) -> JyFrame:
    """
        :param str fp: File path to read
        
        Quick and dirty; reads entire csv with only `shift` data. The result is a bigger file. If you want to make it more efficient, with `fixed` and `shiftIndex` values, then use ``.consolidate()``
    """
    raise Exception("UC")
#/def read_csv

## -- Transformations
##    All return new jyFrames, dicts, items, etc

## -- Filters

def _does_matchRow(
    jyFilter: JyFilter,
    row: dict[ str, any ]
    ) -> bool:
    """
        :param JyFilter jyFilter: Row tester
        :param dict[ str, any ] row: Row to test against `jyFilter`
        
        Checks jyFilter against a row, whether a lambda or a dict
    """
    if isinstance( jyFilter, dict ):
        return all(
            row[ key ] == val for key, val in jyFilter.items()
        )
    #
    if isinstance( jyFilter, Callable ):
        return jyFilter( row )
    #
    raise Exception("Bad jyFilter={}".format( jyFilter ))
#/ def _does_matchRow

def filter(
    jyFrame: JyFrame,
    jyFilter: JyFilter
    ) -> JyFrame:
    """
        :param JyFrame jyFrame: jyFrame to filter
        :param JyFilter jyFilter: Row tester
        
        Gets a new jyFrame with the same header, adding in rows where `jyFilter` is true
    """
    
    new_jyFrame: JyFrame = likeJyFrame( jyFrame )
    if len( jyFrame ) == 0:
        return new_jyFrame
    #
    
    for row in jyFrame:
        if _does_matchRow(
            jyFilter,
            row
        ):
            new_jyFrame.append( row )
        #/if _does_matchRow( ... )
    #/for row in jyFrame
    
    return new_jyFrame
#/def filter

def filter_returnFirst(
    jyFrame: JyFrame,
    jyFilter: JyFilter,
    allow_zero: bool = False
    ) -> dict[ str, any ]:
    """
        :param JyFrame jyFrame: jyFrame to filter
        :param JyFilter jyFilter: Row tester
        :param bool allow_zero: If `True` return an empty dictionary with no matches. If `False` throw an error instead
        
        Return the first row matching the filter. If none match, it will return `{}` if `allow_zero`, otherwise raise.
        
        Used like `filter_expectOne()` except you're very confident there's only one or you need the first. Also useful for finding the first row after a specified time
    """
    if len( jyFrame ) == 0:
        return {}
    #
    
    row: dict[ str, any ]
    for row in jyFrame:
        if _does_matchRow(
            jyFilter,
            row
        ):
            return row
        #/if _does_matchRow( ... )
    #/for row in jyFrame
    
    # Made it here, it means no matches
    if allow_zero:
        return {}
    #
    else:
        raise Exception("No matching rows for jyFilter={}".format( jyFilter ))
    #/if len( new_jyFrame ) >= 1 or allow_zero/else
    raise Exception("Unexpected EOF")
#/def filter_returnFirst

def filter_expectOne(
    jyFrame: JyFrame,
    jyFilter: JyFilter,
    allow_zero: bool = False
    ) -> dict[ str, any ]:
    """
        :param JyFrame jyFrame: jyFrame to filter
        :param JyFilter jyFilter: Row tester
        :param bool allow_zero: If `True` return an empty dictionary with no matches. If `False` throw an error instead
        
        Runs jyFilter but raises if you have more than one result. `allow_zero = True` will return with no results, while
        
        Essentially used when you expect a unique, and present row, sort of like a primary key, and want to double check there's only one matching row. If you trust there will be only one matching row, use `.filter_returnFirst(...)`.
        
        Returns a row as a dict
    """
    
    new_jyFrame: JyFrame = filter( jyFrame, jyFilter )
    
    if len( new_jyFrame ) == 0:
        if allow_zero:
            return {}
        else:
            raise Exception("Zero results")
        #
    #
    
    if len( new_jyFrame ) == 1:
        return new_jyFrame[0]
    #
    
    if len( new_jyFrame ) > 1:
        raise Exception(
            "Too many results;  len( new_jyFrame )={}".format(
                len( new_jyFrame )
            )
        )
    #
    raise Exception("# Bad new_jyFrame={}".format(new_jyFrame))
#/def filter_expectOne

# -- Sorting

def sortedBy(
    jyFrame: JyFrame,
    by: list[ str ]
    ) -> JyFrame:
    """
        :param JyFrame jyFrame: Frame to return new sorted version of
        :param list[ str ] by: Columns by which to sort rows
        
        Returns a new jyFrame, sorting by the values in the `by` list of columns
        Does not change the order of columns at all
    """
    
    
    # Get jyFrame as list of sorted dicts
    # Return into a new jyFrame
    list_sorted = [
        row for row in jyFrame
    ]
    
    list_sorted.sort(
        key = lambda dict: tuple(
            dict[ _key ] for _key in by
        )
    )
  
    new_jyFrame: JyFrame = likeJyFrame( jyFrame )
    for row in list_sorted:
        new_jyFrame.append( row )
    #
    
    return new_jyFrame
#/def sortedBy

# -- Other transformations
def _index(
    shift: list
    ) -> dict[{
        "shift": list[ int ],
        "shiftIndex": list
    }]:
    """
        Gets the shift index representation of a column. Used by ``consolidate()`` to figure out if a column is worth converting to a `fixed` or `shiftIndex` column
    """
    shiftDict: dict[{
        "shift": list[ int ],
        "shiftIndex": list
    }] = {
        "shift": [],
        "shiftIndex": []
    }
    
    for val in shift:
        try:
            # Existent item
            i = shiftDict["shiftIndex"].index( val )
        #
        except ValueError:
            # Not yet present
            i = len( shiftDict["shiftIndex"] )
            shiftDict["shiftIndex"].append( val )
        #/try i = shiftDict["shiftIndex"].index( val )/except ValueError
        
        shiftDict["shift"].append( i )
    #/for val in shift
    return shiftDict
#/def _get_shiftIndex

def _unindex(
    shift: list[ int ],
    shiftIndex: list
    ) -> list:
    """
        Converts a shift indexed column into just a raw list of values, aka a shift column
    """
    return [
        shiftIndex[ key ] for key in shift
    ]
#/def _unidex

def consolidate(
    jyFrame: JyFrame,
    threshold: float|int = 0.5,
    make_fixed: bool = True,
    unindex: bool = True
    ) -> JyFrame:
    """
        :param JyFrame jyFrame: Frame to consolidate and make more efficient
        :param float|int threshold: If the number of unique values is less than, it will be converted to a shiftIndex. Proportion of `len(jyFrame)` if a float, literal number if int.
        :param bool make_fixed: Places columns with a single unique value into `fixed`. If not, it goes into the `shiftIndex` instead.
        :param bool unindex: Whether to convert `shiftIndex` columns to `shift` columns if they surpas threshold in unique count
        
        Checks columns, converting to a shiftIndex when there are few enough unique values (less than `threshold`, as a proportion of `len(jyFrame)` rounded down if a float, literal amount if an int). If there's one unique value, it will become `fixed`, unless `make_fixed = False` in which case it will be in the `shiftIndex`
        
        `shiftIndex` will stay the same if `unindex = False`. `fixed` values will stay fixed. `meta`, `keyTypes`, and `customTypes` will be deepcopied.
        
        
    """
    from copy import deepcopy
    
    threshold_int: int
    if isinstance( threshold, float ):
        from math import ceil
        threshold_int = ceil( threshold * len( jyFrame ) )
    #
    else:
        threshold_int = threshold
    #
    assert threshold_int > 0

    fixed: dict[ str, any ] = {}
    shift: dict[ str, list ] = {}
    shiftIndex: dict[ str, list[ int ] ] = {}
    
    
    for col in jyFrame.keys():
        if col in jyFrame.keys_fixed():
            fixed[ col ] = jyFrame.get_fixed( col )
        #
        elif col in jyFrame._shiftIndex:
            # Check if there are enough unique values to unindex
            if unindex and len( jyFrame._shiftIndex[col] ) >= threshold_int:
                # Many unique values, unindex
                shift[ col ] = _unindex(
                    shift = jyFrame._shift[ col ],
                    shiftIndex = jyFrame._shiftIndex[ col ]
                )
            #
            else:
                # Not enough unique values, leave as shiftIndex
                shiftIndex[ col ] = deepcopy( jyFrame._shiftIndex[ col ] )
                shift[ col ] = deepcopy( jyFrame._shift[ col ] )
            #
        #
        elif col in jyFrame._shift and col not in jyFrame._shiftIndex:
            # Check unique values
            _shiftDict: dict[{
                "shift": list[ int ],
                "shiftIndex": list
            }] = _index( jyFrame._shift[ col ] )
            if make_fixed and len( _shiftDict[ "shiftIndex"] ) == 1:
                # One value, it can be fixed
                fixed[ col ] = _shiftDict["shiftIndex"][ 0 ]
            #
            elif len( _shiftDict[ "shiftIndex" ] ) < threshold_int:
                # Few enough values to index
                shiftIndex[ col ] = _shiftDict["shiftIndex"]
                shift[ col ] = _shiftDict["shift"]
            #
            else:
                # Too many unique values, do not index
                shift[ col ] = deepcopy( jyFrame._shift[ col ] )
            #
        #
        else:
            raise Exception("Bad jyFrame.keys()={}".format( jyFrame.keys() ))
        #/switch col
    #/for col in jyFrame.keys()
    
    return JyFrame(
        fixed = fixed,
        shift = shift,
        shiftIndex = shiftIndex,
        keyTypes = deepcopy( jyFrame._keyTypes ),
        meta = deepcopy( jyFrame._meta ),
        customTypes = deepcopy( jyFrame._customTypes )
    )
#/def consolidate

## -- Second Order stats (Method of moments online estimator)

def fromSecondOrderStats(
    stats: dict[ tuple[any,...], list[float ]],
    groups: list[ str ],
    standard_error: bool = True,
    digits: int = 3
    ) -> JyFrame:
    if len( stats ) == 0:
        return JyFrame()
    #
    
    numerics: list[ str ] = next(
        list( val.keys() ) for val in stats.values()
    )
    
    jyFrame: JyFrame = fromHeaders(
        shiftHeader = numerics,
        shiftIndexHeader = groups
    )
    
    for key, val in stats.items():
        # key: tuple of groups
        # val: { numeric: [ power0, power1, power 2]
        
        row = {}
        
        # Set groups
        for j in range( len(groups ) ):
            row[ groups[j] ] = key[j]
        #
        
        # Set numerics
        for col in numerics:
            row[ col ] = secondOrderString(
                val[ col ],
                standard_error = standard_error,
                digits = digits
            )
        #
        jyFrame.append( row )
    #/for key, val in stats.items()
    
    return jyFrame
#/def fromSecondOrderStats

def secondOrderStats(
    jyFrame: JyFrame,
    groups: list[ str ],
    numerics: list[ str ]
    ) -> dict[ tuple[any,...], list[float ]]:
    """
        Returning dict keys are the values from the keys in `groups` used to index
        
        Returning dict values are dicts with keys the columns from `numerics`, with values a three item list, of the sum of powers 0, 1, and 2 of those numeric values
    """
    summary: dict[
        tuple[any,...],
        dict[
            str,
            list[float]
        ]
    ] = {}
    for row in jyFrame:
        row_key = tuple(
            row[ col ] for col in groups
        )
        if row_key in summary:
            for col in numerics:
                summary[ row_key ][ col ][0] += 1 # Power 0
                summary[ row_key ][ col ][1] += row[ col ] # Power 1
                summary[ row_key ][ col ][2] += row[ col ]**2 # Power 2
            #
        #
        else:
            # New item; initialize each dict
            summary[ row_key ] = {}
            for col in numerics:
                summary[ row_key ][ col ] = [
                    1, # Power 0
                    row[ col ], # Power 1
                    row[ col ]**2 # Power 2
                ]
            #/for col in numerics
        #/if row_key in summary/else
    #/for row in jyFrame
    
    return summary
#/def secondOrderStats
