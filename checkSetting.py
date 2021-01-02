"""@package docstring
"""
#!/usr/bin/python3
# -*- coding: utf-8 -*-

def checkSetting(setting):
    s = str(setting)
    return s.lower() in ['true', '1', 't', 'y', 'yes']

