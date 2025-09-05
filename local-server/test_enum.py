#!/usr/bin/env python3
"""Test NodeType enum behavior"""

import sys
sys.path.append('.')

from database.models import NodeType
from sqlalchemy import Enum as SQLEnum

try:
    print('Testing NodeType enum:')
    print(f'NodeType.LAYER = {NodeType.LAYER!r}')
    print(f'NodeType.DOMAIN = {NodeType.DOMAIN!r}')  
    print(f'NodeType.TERM = {NodeType.TERM!r}')
    
    print(f'\nEnum values:')
    print(f'NodeType.LAYER.value = {NodeType.LAYER.value!r}')
    print(f'NodeType.DOMAIN.value = {NodeType.DOMAIN.value!r}')
    print(f'NodeType.TERM.value = {NodeType.TERM.value!r}')
    
    print(f'\nString comparison:')
    print(f'NodeType.LAYER == "layer": {NodeType.LAYER == "layer"}')
    print(f'NodeType.LAYER.value == "layer": {NodeType.LAYER.value == "layer"}')
    
    # Test creating enum from string
    print(f'\nCreating enum from string:')
    try:
        layer_from_string = NodeType('layer')
        print(f'NodeType("layer") = {layer_from_string!r}')
    except Exception as e:
        print(f'Error creating NodeType from string: {e}')
    
    # Test the SQLEnum column type
    print(f'\nTesting SQLEnum column type:')
    enum_type = SQLEnum(NodeType)
    print(f'SQLEnum(NodeType) created successfully')
    
    # Test if we can get enum values
    print(f'SQLEnum values: {list(NodeType)}')
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
