#!/usr/bin/env python3
"""
Quick test script to validate the LayerBase model fixes
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.layers import LayerBase, LayerCreate

def test_layer_validation():
    print("Testing LayerBase validation...")
    
    # Test 1: Valid layer with definition
    try:
        layer1 = LayerCreate(title="Test Layer", definition="A test layer")
        print("✓ Test 1 passed: Valid layer with definition")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
    
    # Test 2: Valid layer without definition
    try:
        layer2 = LayerCreate(title="Test Layer")
        print("✓ Test 2 passed: Valid layer without definition")
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
    
    # Test 3: Valid layer with empty string definition
    try:
        layer3 = LayerCreate(title="Test Layer", definition="")
        print("✓ Test 3 passed: Valid layer with empty string definition")
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
    
    # Test 4: Invalid layer with short title
    try:
        layer4 = LayerCreate(title="T", definition="A test layer")
        print("✗ Test 4 failed: Should have rejected short title")
    except Exception as e:
        print(f"✓ Test 4 passed: Correctly rejected short title: {e}")

if __name__ == "__main__":
    test_layer_validation()
