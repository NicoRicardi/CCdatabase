#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 14:15:05 2020

@author: nico
"""
import os
import re
import CCDatabase.utils as ut
import numpy as np
import copy as cp
import cachetools
import itertools as ittl

from CCDatabase.utils import caches

@cachetools.cached(cache=caches["npz"])
def cached_load(npzfile):
    return np.load(npzfile, allow_pickle=True)

def vals_from_npz(filepath,key):
    """
    Example of use
    ----
    In [1]: vals = ut.load_js("/home/folder/raws.json" )
    In [2]: print(vals[key])
    [["file.npz",1], ["file.npz",4], ..]
    In [3]: vals = vals_from_npz("/home/folder/file.npz", key)
    In [4]: print(vals)
    [array([0,1,2,3,4]), array([10,20,30,40,50]), ...]
    
    Parameters
    ----------
    filepath: str
        absolute filepath of the npz file
    key: str
        the key to return
    """
    npz = cached_load(filepath)
    return npz[key]


def deal_with_array(arr,to="arr"):
    """
    Note
    ----
    Deals with array-like types
    
    Parameters
    ----------
    arr: list/arr/matrix
        the array-like object to process
    to: str/type
        the desired type.
    
    Returns
    -------
    array-like
        the array like in the requested format
    """
    if type(arr) not in [list, np.ndarray, np.matrix]:
        raise ValueError("It is neither a list, nor an array, nor a matrix")
    options = {"arr": np.array, "array": np.array, "np.array": np.array,
               "np.ndarray": np.array, np.array: np.array,
               "list": list, list: list,
               "matrix": np.matrix, "np.matrix": np.matrix}
    if to not in options.keys():
        raise ValueError("Use one of the options below (str, or function when possible): \n arr, array, np.array, np.ndarray, list")
    to = options[to]
    if type(arr) == to:
        return arr
    elif to != list:
        return to(arr)  # array or matrix
    else:  # to == list
        return arr.tolist()
    
def raw_to_complex(path=None, rawfile="CCParser.json", raw_key="", n=0, 
                   linenumbers=True, first_only=False, group_values=False,
                   arr_type="arr"):
    """
    Note
    ----
    Simply copies a raw quantity as a complex quantity. Handles change of key, picks required "state" (n-th value of raw_quantity)
    
    Parameters
    ----------
    path: str
        path in which to look for raw quantity
    rawfile: str
        the json file with raw quantities. default is ccp
    raw_key: str
        the key of the raw quantity in the json dictionary
    n: int
        which value to take. Uses fortran/human counting, default is 1
    linenumbers: bool
        Whethere the quantity in the json file will have linenumbers. Default is True.
        e.g. json_dict[raw_key]=[[val1,line1],[val2,line2], ...] => use True
             json_dict[raw_key]=[[val1,val2,val3, ...] => use False
     Returns
     -------
     dictionary item
         generally a float, potentially str.
    """
    if not raw_key:
        raise ValueError("you didn't specify the raw quantity's key")
    if n < 0:
        raise ValueError("negative index. Most likely you didn't specify that a quantity is in ex_qs")
    if first_only and n > 0:
        raise ValueError("You want a value only, but are asking for n > 0")
    path = ut.deal_with_type(path, condition=None, to=os.getcwd)
    rawfile = os.path.join(path, rawfile)
    raws = ut.load_js(rawfile)
    vals = raws[raw_key]
    if group_values and np.array([type(i) in [float,np.float32,np.float64] for i in vals]):
        vals = group_values(raws[raw_key])
    val = vals[n][0] if linenumbers else vals[n]
    if type(val) == str and re.match(".+npz", val):
        val = vals_from_npz(os.path.join(path,val), raw_key)[n]
    if type(val) not in [bool, int, float, str]:
        val = deal_with_array(val, to=arr_type)
    return val

def group_values(vals):
    """
    Note
    ----
    if values appear several times with different accuracy, replaces all appearances with the 
    highest number of decimal digits.
    
    Parameters
    ----------
    vals: list
        the values
    
    Returns
    -------
    list
        the values with the updated number of digits
    """
    decimals = lambda x: len(str(x).split(".")[-1])
    options = {n: [] for n in range(len(vals))}
    decs = {n: decimals(vals[n]) for n in range(len(vals))}
    max_d = max(decs.values())
    if min(decs.values()) == max_d:
        return vals
    for n1,v1 in enumerate(vals):
        for n,v2  in enumerate(vals[n1+1:]):  # avoid double iteration (e.g. (0,1),(1,0))
            n2 = n + n1 + 1 # so that v2 = vals[n2]
            if decs[n1] > decs[n2]:
                if round(v1, decs[n2]) == v2:
                    options[n2].append(v1)
            elif decs[n1] < decs[n2]:
                if round(v2, decs[n1]) == v1:
                    options[n1].append(v2)
        if len(set(options[n1])) == 1:
            vals[n1] = options[n1][0]
        elif len(options[n1]) > 1:  # if len(options) == 0 continue
            dlist = [decimals(i) for i in options[n1]]
            dd = {d: dlist.count(d) for d in range(1,max(dlist)+1)}
            to_use = False
            for d in dd.keys():
                rounded = [round(o,d) for o in options[n1] if decimals(o) >= d]
                if len(set(rounded)) != 1:  # all equal if rounded with d decimals
                    break
                to_use = cp.copy(rounded[0])
            vals[n1] = to_use
    return vals

def get_index_dict(s,atomlist):
    """
    """
    l=s.split(",")
    idxs = {}
    for i in l:
        if "-" in i:
            splt = i.split("-")
            al1, al2 = re.search("[A-Za-z]+", splt[0]), re.search("[A-Za-z]+", splt[1])
            al1, al2 = al1.group() if al1 else "", al2.group() if al2 else ""
            assert al1 == al2, "Inconsistent value in atomstring"
            n1, n2 = re.search("[0-9]+", splt[0]).group(), re.search("[0-9]+", splt[1]).group()
            partial = [al1+str(j) for j in range(int(n1),int(n2)+1)]
            vals = []
            for p in partial:
                if p.isalnum():
                    al, n = re.search("[A-Za-z]+", p).group(), int(re.search("[0-9]+", p).group())
                    if al in ["A","a"]:
                        vals.append(n-1)
                    else:
                        try:
                            vals.append([n for n,j in enumerate(atomlist) if j == al][n-1])
                        except:
                            pass  # perhaps logging?
                elif p.isnumeric():
                    raise ValueError("Number in atomstring. Use A1,A2,etc")
                else:
                    raise ValueError("Could not process value in atomstring")
            idxs[i] = vals
        else:
            if i.isalpha():
                idxs[i] = [n for n,j in enumerate(atomlist) if j == i]
            elif i.isalnum():
                al, n = re.search("[A-Za-z]+", i).group(), int(re.search("[0-9]+", i).group())
                if al in ["A","a"]:
                    idxs[i] = [n-1]
                else:
                    try:
                        idxs[i] = [[n for n,j in enumerate(atomlist) if j == al][n-1]]
                    except:
                        idxs[i] = []
            elif i.isnumeric():
                raise ValueError("Number in atomstring. Use A1,A2,etc")
            else:
                raise ValueError("Could not process value in atomstring")
    return idxs

def raw_atomic(path=None, atomstring="", n=0, rawfile="CCParser.json", 
               raw_key="", first_only=True, frag=0, all_frag_avail=True,
               linenumbers=True, arr_type="arr"):
    """
    Note
    ----
    Returns an atomic quantity. Uses the geometry to deduce value index.
    
    Parameters
    ----------
    path: str
        the folder path 
    atomstring: str
        a string which determines which atoms to select.
        "O" => every oxygen
        "O1" => the first oxygen
        "O2-O4" => oxygen 2,3,4
        "A1", "A2-A4": atom 1, atom 2,3,4
    n: int
        the state (0=GS,1=ES1, ..)
    rawfile: str
        the name of the raw quantity json file
    raw_key: str
        the desired property's key
    first_only: bool
        if the property is only GS
    frag: int
        what fragment the counting should be in
    all_frag_avail: bool
        whether the property is available only for frag_0 or all
    linenumbers: bool
        whether raw quantities include the linenumber or not
    arr_typ: str/type
        desired type of array-like objects
    
    Returns
    -------
    obj
        the property. if array-like, in the desired format
    """
    if not raw_key:
        raise ValueError("you didn't specify the raw quantity's key")
    if n < 0:
        raise ValueError("negative index. Most likely you didn't specify that a quantity is in ex_qs")
    if first_only and n > 0:
        raise ValueError("You want a value only, but are asking for n > 0")
    path = ut.deal_with_type(path, condition=None, to=os.getcwd)
    rawfile = os.path.join(path, rawfile)
    raws = ut.load_js(rawfile)
    if "frag_xyz" in raws.keys():
        geomkey = "frag_xyz"
    elif "xyz" in raws.keys():
        geomkey = "xyz"
        if frag:
            raise ValueError("fragment geometries not available")
    else:
        raise ValueError("no type of geometry (frag_xyz/xyz) available")
    geoms = raws[geomkey][0][0]
    if  re.match(".+npz", geoms):
        npzfile = os.path.join(path,geoms)
        geoms = vals_from_npz(npzfile, geomkey)
    else:
        if geomkey == "frag_xyz":
            geoms = [np.array(geom, dtype="object") for geom in geoms]
        else:
            geoms = np.array(geoms, dtype="object")
    if geomkey == "frag_xyz": 
        frag_atoms = geoms[frag][:,0]
        all_atoms = np.vstack(*geoms)[:,0]
        shift = sum([len(geom) for geom in geoms[:frag]])  # N_atoms in fragments before frag
    else:
        frag_atoms = geoms[:,0]
        all_atoms = frag_atoms
    all_vals = raws[raw_key]
    atomlist = all_atoms if all_frag_avail else frag_atoms
    if len(all_vals)%len(atomlist) != 0:
        raise AssertionError("The total number of values available is not a multiple of the number of atoms!")
    idict = get_index_dict(atomstring, atomlist)
    valsdict = {}
    for name,idxs in idict.items():
        idxs = [idx + n*len(atomlist) + shift for idx in idxs]  # adjust for state and previous fragments
        try:
            vals = [all_vals[idx][0] if linenumbers else all_vals[idx] for idx in idxs]
        except:
            vals = []
        for nv, val in enumerate(vals):
            if  type(val) == str and re.match(".+npz", val):
                vals[nv] = vals_from_npz(os.path.join(path,val), raw_key)[idxs[nv]]
            if type(vals[nv]) not in [bool, int, float]:
                vals[nv] = deal_with_array(vals[nv], to=arr_type)
        valsdict[name] = vals
    if not list(ittl.chain.from_iterable(valsdict.values())):
        raise BaseException("No item in atomstring returned a quantity value")
    to_return = valsdict.copy()    
    for k,v in valsdict.items():
        if not v:
            del to_return[k]
    return to_return
    
"""
for quantity functions it is often useful to use some general function with several parameters,
define all of them but "path" and "n" into a lambda function, which is then saved as quantity function.
e.g. 
"ex_en": lambda path, n: raw_to_complex(path=path, n=n, rawfile="CCParser.json", raw_key="exc_energies_rel")
"""
ccp_funcs = {
        "ex_en": lambda path,n: raw_to_complex(path=path, n=n-1, rawfile="CCParser.json", raw_key="exc_energy_rel"),
        "osc": lambda path,n: raw_to_complex(path=path, n=n-1, rawfile="CCParser.json", raw_key="osc_str"),
        "SCF": lambda path,n: raw_to_complex(path=path, n=n, rawfile="CCParser.json", raw_key="scf_energy", first_only=True)
        }

qcep_ccp_funcs = {
        "ex_en": lambda path,n: raw_to_complex(path=path, n=n-1, rawfile="CCParser.json", raw_key="exc_energy"),
        "osc": lambda path,n: raw_to_complex(path=path, n=n-1, rawfile="CCParser.json", raw_key="osc_strength"),
        "SCF": lambda path,n: raw_to_complex(path=path, n=n, rawfile="CCParser.json", raw_key="scf_energy", first_only=True),
        "EFG_e":lambda path, atomstring, n:\
        {k: np.linalg.eigvals(v).tolist() for k,v in\
         raw_atomic(path=path, atomstring=atomstring, n=n, rawfile="CCParser.json", raw_key="EFG_tensor_e", first_only=True, arr_type="arr").items()},
         "EFG_n":lambda path, atomstring, n:\
        {k: np.linalg.eigvals(v).tolist() for k,v in\
         raw_atomic(path=path, atomstring=atomstring, n=n, rawfile="CCParser.json", raw_key="EFG_tensor_n", first_only=True, arr_type="arr").items()},
        "EFG_t":lambda path, atomstring, n:\
        {k: np.linalg.eigvals(v).tolist() for k,v in\
         raw_atomic(path=path, atomstring=atomstring, n=n, rawfile="CCParser.json", raw_key="EFG_tensor_t", first_only=True, arr_type="arr").items()}
        }

qcep_funcs = {
        "ex_en": lambda path,n: raw_to_complex(path=path, n=n-1, rawfile="qcep.json", raw_key="exc_energy"),
        "osc": lambda path,n: raw_to_complex(path=path, n=n-1, rawfile="qcep.json", raw_key="osc_strength"),
        "SCF": lambda path,n: raw_to_complex(path=path, n=n, rawfile="qcep.json", raw_key="scf_energy", first_only=True),
        "EFG_e":lambda path, atomstring, n:\
        {k: np.linalg.eigvals(v).tolist() for k,v in\
         raw_atomic(path=path, atomstring=atomstring, n=n, rawfile="qcep.json", raw_key="EFG_tensor_e", first_only=True, arr_type="arr").items()},
         "EFG_n":lambda path, atomstring, n:\
        {k: np.linalg.eigvals(v).tolist() for k,v in\
         raw_atomic(path=path, atomstring=atomstring, n=n, rawfile="qcep.json", raw_key="EFG_tensor_n", first_only=True, arr_type="arr").items()},
        "EFG_t":lambda path, atomstring, n:\
        {k: np.linalg.eigvals(v).tolist() for k,v in\
         raw_atomic(path=path, atomstring=atomstring, n=n, rawfile="qcep.json", raw_key="EFG_tensor_t", first_only=True, arr_type="arr").items()}
        }

