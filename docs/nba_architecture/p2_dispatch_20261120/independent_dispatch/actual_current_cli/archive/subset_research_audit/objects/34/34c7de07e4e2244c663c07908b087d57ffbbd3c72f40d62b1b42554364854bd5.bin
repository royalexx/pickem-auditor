"""Strict wire helpers shared by the opt-in subset handoffs."""
import json


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('DUPLICATE_SUBSET_KEY')
            result[key]=value
        return result
    def nonfinite(value):raise ValueError('NONFINITE_SUBSET_VALUE')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=nonfinite)
