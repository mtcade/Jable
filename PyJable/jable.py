#
"""
    A number row, named column alternative to csv, instead storing the object as json
    
    This permits more complex objects, by allowing any type as an object, and storing anything which can be serialized as an item in a json list
    
    For maximal reliability, imports only the standard library
    
"""

import json

from collections.abc import Iterable, MutableSequence
from typing import Callable, Literal, Self
from sys import path

# Dictionary representation of the data in a JFrame
JFrameDict: type = dict[{
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

# JFilter: A way to check if rows match some criterion, either by equality with every value in a dictionary, or evaluating as true with a lambda taking the row dictionary as an input
JFilter: type = dict[ str, any ] | Callable[ dict[ str, any ], bool ]

def row_does_matchJFilter(
    row: dict[ str, any ],
    jFilter: JFilter
    ) -> bool:
    """
        The way to check if a row dictionary matches a jFilter
        
        For dictionaries, check equality on every key
        
        For Callables, just run the Callable on the row
    """
    if isinstance( jFilter, dict ):
        return all(
            row[ key ] == jFilter[ key ] for key in jFilter
        )
    #
    
    if isinstance( jFilter, Callable ):
        return jFilter( row )
    #
    
    raise Exception("Unrecognized jFilter={}".format(jFilter))
#/def row_does_matchJFilter

class JFrame():
    """
        Stores column data as a combination of three parts:
        
        :param dict[ str, any ] fixed: Columns with the same name for value in every row. You can change its value but that will essentially change it for every row; try to only change it in code that knows it's a fixed key, and sets and gets it with the fixed methods (`.keys_fixed()`, `.get_fixed(...)`)
        :param dict[ str, list ] shift: Where we have a listed literal item as a value, typically a string, float or int, sometimes lists of them, sometimes dictionaries or any other objects
        :param dict[ str list ] shiftIndex: Sometimes, shift columns will have the same value repeated many times. If its column name is in shift index, then the values in shift are integers, referring to the index in shiftIndex of the same column. I.e., if we have `shift["fur_color"] = [1,0,2]` and `shiftIndex["fur_color"] = ["green","orange","purple","red"]`, then the `"fur_color"`s are really `["orange","green","purple"]`
        :param dict[ str, str | type ] keyTypes: Optional types to set for any columns. No enforcement is done by the JFrame itself, whether inserting or retriving. It is for your own use. These will be serialized as strings using `str` so add the appropriate functions for custom classes to serialize it as you want, and convert into a class upon reading. Includes support for basic python types
        :param dict[ str, any ] meta: Another arbitrary dictionary to hold domain specific data, in the table as `._meta`. No methods write or use this, so edit and read at will or subclass.
        :param dict[ str, type ] customTypes: A reference to use for deserializing string types from `keyTypes`. Gets checked before builtin types
        
        For `table: JFrame` You can get a column `my_column: str` of data by taking `table[my_column]`. You can get a row `j: int` as a dictionary with `table[j]`. You can get one item with `table[j,my_column]`; see `.__getitem__(...)`
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
        for col, _type in keyTypes:
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
    
    def __len__( self: Self ) -> int:
        return self._len
    #
    
    def keys( self: Self ) -> list[ str ]:
        """
            Gets the equivalent of all column names of the table, including fixed and nonfixed
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
    
    # -- Getting and Iterating
    
    def __iter__( self: Self ) -> "JFrameIterator":
        """
            Goes through by row giving each row as a dictionary
        """
        return JFrameIterator( self )
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
    
    def __getitem__( self: Self, index: int | str | tuple[ int | slice, str ] | list[ str | int ] ) -> any:
        """
            table[ i: int, col: str ]
                -> any (specific value in table)
            table[ i: int | Iterable[ int ] ]
                -> Dictionary of row
            table[ col:str ] | table[ rows: Iterable | Slice, col:str ]
                -> List of items
            table[ rows: Iterable[int] | Slice, cols: Iterable[ str ] )
                -> JFrame
        """
        if isinstance( index, tuple ):
            assert len( index ) == 2
            # TODO: handle slices for first item, iterables for second
            row = index[0]
            if isinstance( row, int ):
                row = [ row ]
            #
            elif isinstance( row, slice ):
                # Row is a slice
                # Convert row to indices
                row = [i for i in range( *row.indices(self._len) ) ]
            elif isinstance( row, Iterable ):
                # List of ints, most likely
                ...
            #
            else:
                raise Exception("bad row={}".format( row ) )
            #
            
            column = index[1]
            if isinstance( column, Iterable ):
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
                elif len( row ) > 1:
                    return JFrame(
                        fixed = {
                            col: val for col, val in self._fixed.items() if col in column
                        },
                        shift = {
                            col: [
                                self._shift[ col ][ i ] for i in row
                            ] for col in column if col in self._shift
                        },
                        shiftIndex = {
                            col: self._shiftIndex[ col ] for col in column if col in self._shiftIndex
                        },
                        meta = self._meta
                    )
                #
                else:
                    raise Exception("# Bad row={}".format(row))
                #/switch len( row )
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
            else:
                # TODO: return new table if column is iterable
                raise Exception("Bad column={}".format( column ))
            #
        #
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
        else:
            raise Exception("Bad index={}".format(index))
        #/switch { type( index ) }
    #/def __getitem__
    
    def get_fixed( self: Self, key: str, default: any = None ) -> any:
        """
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
            Allows programs to give a default value for keys which are not in `_fixed`, and otherwise gives the `_fixed` values. This saves the headache of repeatedly checking `.keys_fixed()`
        """
    #/def get_fixed_withDefaultDict
    
    def as_dict( self: Self ) -> JFrameDict:
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
    
    def does_matchIndex(
        self: Self,
        jFilter: JFilter,
        index: int
        ) -> bool:
        """
            Check to see if a row matches a given jFilter
        """
        return row_does_matchJFilter(
            row = self[ index ],
            jFilter = jFilter
        )
    #/def does_matchIndex
    
    def any_matchingIndices(
        self: Self,
        jFilter: JFilter
        ) -> bool:
        """
            Says if at least one row matches jFilter
        """
        if isinstance( jFilter, dict ):
            fixed_keys = [ key for key in jFilter if key in self._fixed ]
            if not all( self._fixed[key] == jFilter[key] for key in fixed_keys ):
                return False
            #
        #
        
        return any(
            self.does_matchIndex(
                jFilter = jFilter,
                index = index
            ) for index in range( len( self ) )
        )
        return False
    #/def any_matchingIndices
    
    def get_matchingIndices(
        self: Self,
        jFilter: JFilter
        ) -> list[ int ]:
        """
            Get a list of indices which match jFilter
        """
        if isinstance( jFilter, dict ):
            fixed_keys = [ key for key in jFilter if key in self._fixed ]
            if not all( self._fixed[key] == jFilter[key] for key in fixed_keys ):
                return []
            #
        #
        
        return [
            index for index in range( len( self ) ) if self.does_matchIndex(
                jFilter = jFilter,
                index = index
            )
        ]
    #/def get_matchingIndices
    
    
    # -- Modification
    
    def _set_index_withDict( self: Self, index: int, row: dict ) -> None:
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
    
    def _set_fixed( self: Self, col: str, newvalue: any ) -> None:
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
    
    # TODO: More cases on index, row
    def __setitem__( self: Self, index: int, newvalue: any ) -> None:
        """
            Used in three primary ways:
            
            `table[ row: int, col: str ] = newVal: any`: Set single value
            `table[ row: int ] = newRow: dict`: Set new row
            `table[ col: str ] = newVal: any`, with `col` in `self._fixed.keys()`: Set a fixed value
            `table[ col: str ] = newColumn: list[ any ]`: Set entirety of new column
            `table[ col: str ] = rowsDict: dict[ row: int, newvalue: any ]`: for a dictionary indexed by integers, set those rows for `col` to be the value in the dict
        """
        if isinstance( index, int ) and isinstance( newvalue, dict ):
            self._set_index_withDict( index = index, row = newvalue )
            return
        #
        elif isinstance( index, str ):
            if index in self._fixed:
                self._set_fixed( col = index, row = newvalue )
                return
            #
            if isinstance( newvalue, list ):
                self._set_column_withList( col = index, newList = newvalue )
                return
            #
            if isinstance( newvalue, dict ):
                self._set_column_withDict( col = index, newDict = newvalue )
                return
            #
            raise Exception("Unrecognized index={}, newvalue={}".format( index, newvalue ))
        #
        elif isinstance( index, tuple ):
            # row, col
            assert len( tuple ) == 2
            self._set_index_withDict( index[0], { index[1]: newvalue } )
            return
        #
        else:
            raise Exception(
                "Unrecognized index={}, newvalue={}".format(
                    index, newvalue
                )
            )
        #/switch { class(index), class( newvalue ) }
    #/def __setitem__
    
    def insert( self: Self, index: int, value: dict[ str, any ] ) -> None:
        # Insert `None` at the index for each shift value, then set via __setitem
        for key in self._shift.keys():
            self._shift[ key ].insert( index, None )
        #
        self._len += 1
        self.__setitem__( index = index, newvalue = value )
    #/def insert
    
    def set_where(
        self: Self,
        jFilter: JFilter,
        row: dict[ str, any ],
        limit: int | None = None,
        verbose: int = 0
    ) -> None:
        """
            Update every row with the given literal row, if it matches jFilter
            
            You can set a max number of rows to be updated, speeding things up by ending early
        """
        if limit is None:
            limit = len( self )
        #
        
        if isinstance( jFilter, dict ):
            # Convert dict to proper selection
            _lambda = lambda _row: all( _row[ key ] == val for key, val in jFilter.items() )
        #
        else:
            _lambda = jFilter
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
        if strict:
            # 2025-02-13: Unintuitive behavior when inserting a row
            #    which just happens to have a fixed value in it
            #assert not any( key in self._fixed for key in row )
            assert all( key in self.keys() for key in row )
            # Make sure fixed values match
            for key in self._fixed:
                if key in row:
                    assert row[key] == self._fixed[key]
                #/if key in row
            #/for key in self._fixed
            
            for key, val in row.items():
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
            # Update fixed if present
            for key in self._fixed:
                if key in row:
                    self._fixed[ key ] = row[ key ]
                #
            #/for key in self._fixed
        #/if strict/else
        self._len += 1
        self.shape = ( self._len, self.shape[1])
        return
    #/def append
    
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
        jFilter: JFilter
        ) -> None:
        """
            Remove indices matching jFilter via `.get_matchingIndices`
        """
        # Have to change indices as we remove them
        # Since we go from low to high, subtract 1 from the matching index for each
        #   index previously removed
        matchingIndices: list[ int ] = self.get_matchingIndices(
            jFilter
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
            Standard method to write to a file as a json, which can be initialized into a table via `fromDict(...)` after reading
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
#/class JFrame

class JFrameIterator():
    def __init__(
        self: Self,
        table: JFrame
    ):
        self._index = 0
        self._table = table
    #
    
    def __next__( self: Self ) -> dict:
        if self._index > len( self._table ) - 1:
            raise StopIteration
        #
        else:
            self._index += 1
            return self._table._fixed | {
                key: self._table._shiftIndex[ key ][ val[ self._index-1 ] ] \
                    for key, val in self._table._shift.items() if key in self._table._shiftIndex
            } | {
                key: val[ self._index-1 ] \
                    for key, val in self._table._shift.items() if key not in self._table._shiftIndex
            }
        #/if self._index > len( self._table ) - 1/else
    #/def __next__
#/class JFrameIterator

# -- Initializers

def fromDict(
    jFrame: JFrameDict
    ) -> JFrame:
    """
        Converts the raw json to JFrame, without adding any structure
    """
    return JFrame(
        fixed = data["_fixed"],
        shift = data["_shift"],
        shiftIndex = data["_shiftIndex"],
        keyTypes = data["_keyTypes"],
        meta = data["_meta"]
    )
#/def fromDict

def fromShiftIndexHeader(
    fixed: dict[ str, any ] | list[ str ] = {},
    shift: dict[ str, list ] = {},
    shiftIndexHeader: list[ str ] = [],
    keyTypes: dict[ str, type ] = {},
    meta: any = {}
    ) -> JFrame:
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
    
    table: JFrame = JFrame(
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
        return table
    #
    
    # Add items
    _len: int = len(
        next(
            _val for _val in shift.values()
        )
    )
    
    for i in range( _len ):
        table.append(
            {
                _key: _val[ i ] for _key, _val in shift.items()
            }
        )
    #
    
    return table
#/def fromShiftIndexHeader

def fromHeaders(
    fixed: dict[ str, any ] | list[ str ] = {},
    shiftHeader: list[ str ] = [],
    shiftIndexHeader: list[ str ] = [],
    keyTypes: dict[ str, type ] = {},
    meta: any = {}
    ) -> JFrame:
    """
        Initializes a table with the given headers, but no data (with the possible exception of `fixed`)
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
    
    return JFrame(
        fixed = fixed,
        shift = { col: [] for col in shiftHeaderAll },
        shiftIndex = { col: [] for col in shiftIndexHeader },
        keyTypes = keyTypes,
        meta = meta
    )
#/def fromHeaders

def fromDict_shift( data: dict[ str, list ] ) -> JFrame:
    return JFrame( shift = data )
#/def fromDict_shift

def likeTable(
    table: JFrame
    ) -> JFrame:
    """
        Gives a blank table with copied headers
    """
    return fromHeaders(
        fixed = table._fixed,
        shiftHeader = [
            key for key in table._shift.keys()
        ],
        shiftIndexHeader = [
            key for key in table._shiftIndex.keys()
        ],
        keyTypes = table._keyTypes,
        meta = table._meta
    )
#/def likeTable

def fromFile(
    fp: str,
    decoder: json.JSONDecoder | None = None,
    strict: bool = False,
    update: bool = False
    ) -> JFrame:
    """
        Reads directly as a table on the disk in json form
    """
    with open( fp, 'r' ) as _file:
        data: JFrameDict = json.load( fp = _file, cls = decoder )
    #
    
    data_all: JFrameDict
    
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

        data_all = {
            key: {} for key in _REQUIRED_KEYS
        } | data
    #
    else:
        data_all = {
            key: {} for key in _REQUIRED_KEYS
        } | data
    #/if strict/else
    
    jFrame: JFrame = fromDict( data_all )
    
    # Write file if it's missing a section and
    if update and any( key not in data for key in _REQUIRED_KEYS ):
        jFrame.write_file( file = file )
    #
    
    return jFrame
#/def fromFile

# Synonoym: fromFile
def from_file( fp: str, decoder: json.JSONDecoder | None = None ) -> JFrame:
    """
        Directly reads from a regular json on the disc. Synonym to `fromFile()`
    """
    return fromFile( fp = fp, decoder = decoder )
#/def fromFile

def fromFile_shift( fp: str, decoder: json.JSONDecoder | None = None ) -> JFrame:
    """
        Reads the table as the shift data only, with no fixed and no meta
        
        This is a niche use, for when a table has been stored as a dictionary of lists at the top level
    """
    with open( fp, 'r' ) as _file:
        data: dict = json.load( fp = _file, cls = decoder )
    #
    
    return fromDict_shift( data )
#/def fromFile_shift

## -- Transformations, filters
##    All return new tables, dicts, items, etc

def _does_matchRow(
    jFilter: JFilter,
    row: dict[ str, any ]
    ) -> bool:
    """
        Checks jFilter against a row, whether a lambda or a dict
    """
    if isinstance( jFilter, dict ):
        return all(
            row[ key ] == val for key, val in jFilter.items()
        )
    #
    if isinstance( jFilter, Callable ):
        return jFilter( row )
    #
    raise Exception("Bad jFilter={}".format( jFilter ))
#/ def _does_matchRow

def filter(
    table: JFrame,
    jFilter: JFilter
    ) -> JFrame:
    """
        Gets a new table with the same header, adding in rows where `jFilter` is true
    """
    
    new_table: JFrame = likeTable( table )
    if len( table ) == 0:
        return new_table
    #
    
    for row in table:
        if _does_matchRow(
            jFilter,
            row
        ):
            new_table.append( row )
        #/if _does_matchRow( ... )
    #/for row in table
    
    return new_table
#/def filter

def filter_returnFirst(
    table: JFrame,
    jFilter: JFilter,
    allow_zero: bool = False
    ) -> dict[ str, any ]:
    """
        Return the first row matching the filter. If none match, it will return `{}` if `allow_zero`, otherwise raise.
        
        Used like `filter_expectOne()` except you're very confident there's only one or you need the first. Also useful for finding the first row after a specified time
    """
    new_table: JFrame = likeTable( table )
    if len( table ) == 0:
        return new_table
    #
    
    
    for row in table:
        if _does_matchRow(
            jFilter,
            row
        ):
            new_table.append( row )
            break
        #/if _does_matchRow( ... )
    #/for row in table
    
    if len( new_table ) >= 1 or allow_zero:
        return new_table
    #
    else:
        raise Exception("No matching rows for jFilter={}".format( jFilter ))
    #/if len( new_table ) >= 1 or allow_zero/else
    
    raise Exception("Unexpected EOF")
#/def filter_returnFirst

def filter_expectOne(
    table: JFrame,
    jFilter: JFilter,
    allow_zero: bool = False
    ) -> dict[ str, any ]:
    """
        Runs jFilter but raises if you have more than one result. `allow_zero` will return `{}` if true, otherwise will also raise with zero results
        
        Essentially used when you expect a unique, and present row, sort of like a primary key
        
        Returns a row as a dict
    """
    
    new_table: JFrame = filter( table, jFilter )
    
    if len( new_table ) == 0:
        if allow_zero:
            return {}
        else:
            raise Exception("Zero results")
        #
    #
    if len( new_table ) == 1:
        return new_table[0]
    #
    
    if len( new_table ) > 1:
        raise Exception("Too many results ({})".format( len_new_table ) )
    #
    raise Exception("# Bad new_table={}".format(new_table))
#/def filter_expectOne

# -- Sorting

def sortedBy(
    table: JFrame,
    by: list[ str ]
    ) -> JFrame:
    """
        Returns a new table, sorting by the values in the `by` list of columns
        Does not change the order of columns at all
    """
    
    
    # Get table as list of sorted dicts
    # Return into a new table
    list_sorted = [
        row for row in table
    ]
    
    list_sorted.sort(
        key = lambda dict: tuple(
            dict[ _key ] for _key in by
        )
    )
  
    newTable: JFrame = likeTable( table )
    for row in list_sorted:
        newTable.append( row )
    #
    
    return newTable
#/def sortedBy

## -- Second Order stats (Method of moments online estimator)

def fromSecondOrderStats(
    stats: dict[ tuple[any,...], list[float ]],
    groups: list[ str ],
    standard_error: bool = True,
    digits: int = 3
    ) -> JFrame:
    if len( stats ) == 0:
        return JFrame()
    #
    
    numerics: list[ str ] = next(
        list( val.keys() ) for val in stats.values()
    )
    
    table: JFrame = fromHeaders(
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
        table.append( row )
    #/for key, val in stats.items()
    
    return table
#/def fromSecondOrderStats

def secondOrderStats(
    table: JFrame,
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
    for row in table:
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
    #/for row in table
    
    return summary
#/def secondOrderStats
