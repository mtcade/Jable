"""
    Utilities to read and print json tables
    
    Inject jable.JFrame as needed; we use the Protocol `Table`
"""

from typing import Literal, Protocol, runtime_checkable, Self
from abc import abstractmethod
#from collections.abc import MutableSequence

# -- Settings
# Maximum length of string to print if inferred from table
_DEFAULT_MAX_STR_LEN: int = 50

@runtime_checkable
class Table( Protocol ):
    """
        Interface for JsonTable
        
        Conforms to collections.abc.MutableSequence:
            __len__
            __getitem__
            __setitem__
            __delitem__
            insert
    """
    
    # -- collections.abc.MutableSequence
    def __len__( self: Self ) -> int:
        raise NotImplementedError()
    #
    
    def __getitem__( self: Self, index: int ) -> dict[ str, any ]:
        raise NotImplementedError()
    #
    
    def __setitem__( self: Self, index: int, value: dict[ str, any ] ) -> None:
        raise NotImplementedError()
    #
    
    def __delitem__( self: Self, index: int ) -> None:
        raise NotImplementedError()
    #
    
    def insert( self: Self, index: int, value: dict[ str, any ] ) -> None:
        raise NotImplementedError()
    #
    
    @abstractmethod
    def keys( self: Self ) -> list[ str ]:
        raise NotImplementedError()
    #
    
    @property
    @abstractmethod
    def _fixed( self: Self ) -> dict[ str, any ]:
        raise NotImplementedError
    #
    
    @property
    @abstractmethod
    def _shiftIndex( self: Self ) -> dict[ str, list ]:
        raise NotImplementedError
    #
    
    @property
    @abstractmethod
    def _shift( self: Self ) -> dict[ str, list ]:
        raise NotImplementedError
    #
#/class Table

## -- Display

## -- Display Helpers
def _set_stringToLen(
    val: any,
    length: int
    ) -> str:
    return ( ' '*length + str( val ))[-1*length:]
#

def _get_rowList(
    row: list,
    column_width: list[ int ]
    ) -> list[ str ]:
    """
        Cuts down each item in row to a string of the appropriate width
    """
    return [
        _set_stringToLen( row[j], column_width[j] ) for j in range( len(row) )
    ]
#/def _get_rowList

def _maxLen_forKey(
    table: Table,
    key: str
    ) -> int:
    key_len: int = len( key )
    
    # If the table has no rows, we can ignore values, such as in fixed, which might appear
    if len( table ) <= 0:
        return min( key_len, _DEFAULT_MAX_STR_LEN )
    #
    
    if key in table._fixed:
        _len = max( key_len, len( str(table._fixed[key]) ) )
    #
    elif key in table._shiftIndex:
        if len( table._shiftIndex[ key ] ) > 0:
            _len = max(
                len( str(val) ) for val in table._shiftIndex[ key ]
            )
            _len = max( _len, key_len )
        #
        else:
            _len = key_len
        #/if len( table._shiftIndex[ key ] ) > 0/else
    #
    elif key in table._shift and key not in table._shiftIndex:
        if len( table._shift[ key ] ) > 0:
            _len = max(
                len( str(val) ) for val in table._shift[ key ]
            )
            _len = max( _len, key_len )
        else:
            _len = key_len
        #/if len( table._shift[ key ] ) > 0
    #
    else:
        raise Exception("Missing key={}".format(key))
    #
    return min( _len, _DEFAULT_MAX_STR_LEN )
#/def _maxLen_forKey

def _get_stringLength(
    table: Table,
    key: str,
    length: int | None | str
    ) -> int:
    
    if length is None:
        return len( key )
    #
    
    if isinstance( length, int ):
        return length
    #

    if isinstance( length, str ):
        if length == 'max':
            return _maxLen_forKey( table, key )
        #
        else:
            raise Exception("Unexpected length operator={}".format( length) )
        #
    #
#/def _get_stringLength

# -- Interface

def prettyprint(
    table: Table | list | dict,
    columns: list[ str ] = [],
    column_width: int | str | list[ int | None ] | dict[ str, int ] = [],
    max_rows: int | None = None
    ) -> None:
    """
        Prints a display of the given columns lined up. If no columns provided, prints all.
        
        Will simply print lists, dictionaries, or not `Table` items, since they can appear as parts of tables as columns, rows, or items.
    """
    # Handle non `Table` (JyFrame) items
    if isinstance( table, list | dict ):
        print( table )
        return
    #
    elif not isinstance( table, Table ):
        print( table )
        return
    #
    
    if columns == []:
        columns = table.keys()
    #
    
    if column_width == []:
        column_width = [
            _maxLen_forKey( table = table, key = key ) for key in columns
        ]
    #
    elif isinstance(
        column_width,
        int
    ) or isinstance( column_width, str ):
        column_width = [
            _get_stringLength(
                table = table,
                key = col,
                length = column_width
            ) for col in columns
        ]
    #
    elif isinstance( column_width, list ):
        assert len( column_width ) == len( columns )
        # Might have none for some
        for j in range( len( column_width ) ):
            column_width[ j ] = _get_stringLength(
                table = table, key = columns[j], length = column_width[j]
            )
        #
    #
    elif isinstance( column_width, dict ):
        column_width = [
            _get_stringLength(
                table = table,
                key = key,
                length = column_width[ key ]
            ) if key in column_width else len( key ) for key in columns
        ]
    else:
        raise Exception("Unrecognized column_width={}".format(column_width))
    #/switch column_width
    
    if max_rows is None:
        max_rows = len( table )
    #
    
    # Header
    next_list: list[ str ]
    
    next_list = _get_rowList(
        columns, column_width
    )
    print( ' '.join( next_list ) )
    
    # Divider
    next_list = [
        '-'*len( _item ) for _item in next_list
    ]
    print( ' '.join( next_list ) )
    
    # data
    for i in range( min( max_rows, len(table) ) ):
        next_list = _get_rowList(
            [ table[i][ col ] for col in columns ],
            column_width
        )
        
        print( ' '.join( next_list ) )
    #
    
    return
#/def prettyprint

def format_decimal(
    string: str,
    digits: int = 3
    ) -> str:
    """
        Takes a decimal string, pads with spaces on the left, zeros on the right if there is a point
    """
    string_out: str
    if '.' in string:
        string_split = string.split('.')
        string_split[1] = string_split[1].ljust( digits, '0' )
        string_out = '.'.join( string_split )
    #
    else:
        string_out = string.rjust( digits, ' ' )
    #
    return string_out
#/def format_decimal

def secondOrderString(
    soStats: list[ float ],
    standard_error: bool = True,
    digits: int = 3
    ) -> str:
    from math import sqrt
    
    mean: float = soStats[1]/soStats[0]
    var: float = soStats[2]/soStats[0] - mean**2
    
    mean_str: str = format_decimal(
        str( round( mean, digits ) ),
        digits = digits
    )
    
    error_str: str
    if standard_error:
        error_str = str(
            round(
                sqrt( var/soStats[0] ),
                digits
            )
        )
    #
    else:
        error_str = str(
            round( sqrt( var ), digits )
        )
    #/if standard_error/else
    error_str = format_decimal(
        error_str,
        digits = digits
    )
    
    return '{} ({})'.format( mean_str, error_str )
#/def secondOrderString

def prettyprint_secondOrderStats_table(
    table: Table,
    max_rows: int | None = None
    ) -> None:
    """
        Automatically uses max for column widths
        
        The numerics are already assumed to be trimmed strings
    """
    return prettyprint(
        table = table,
        column_width = 'max',
        max_rows = max_rows
    )
#/def prettyprint_secondOrderStats

def _latex_str(
    string: str
    ) -> str:
    """
        Makes a string suitable for latex printing
        
        - removes underscores
    """
    
    string_out = string.replace('_'," ")
    return string_out
#

def latexprint_table(
    table: Table,
    columns: list[ str ] | None = None,
    column_alignment: dict[ str, Literal['c','l','r'] ] = {},
    max_rows: int | None = None
    ) -> None:
    """
        Prints a LaTeX table
        
        Does not include table and centering, just tabular
    """
    if columns is None:
        columns = table.keys()
    #
    
    if max_rows is None:
        max_rows = len( table )
    #
    else:
        max_rows = min( max_rows, len(table) )
    #
    
    # Default column alignment is 'c'
    column_alignment = {
        col: 'c' for col in columns
    } | column_alignment
    
    # Tabluar start
    # { c c c }
    alignment: str = "{ " + " ".join(
        column_alignment[ col ] for col in columns
    ) + " }"
    print(r"\begin{tabular}" + alignment)
    
    # Header
    print(
        "  " + " & ".join(
            _latex_str( col ) for col in columns
        ) + r" \\"
    )
    print(r"  \hline")
    
    # Rows
    # Don't need to format lengths since latex deals with it
    for i in range( max_rows ):
        row = table[i]
        row_str = "  " + " & ".join(
            _latex_str( row[ key ] ) for key in columns
        )
        if i < max_rows - 1:
            row_str = row_str + r" \\"
        #
        
        print( row_str )
    #/for i in range( max_rows )
    
    # Tablular End
    print(r"\end{tabular}")
#/def latexprint_table
