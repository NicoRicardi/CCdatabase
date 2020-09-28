"""Some useful tools to comunicate with other QC software."""

import os
import re
import json
import numpy as np
from CCParser.QChem import extract_floats, parse_symmetric_matrix#, parse_inline_vec


def parse_molecule(n, readlin):
    """Parse the geometry of all fragements in one file.

    Parameters
    ----------
    n : int
        Line number of identifier
    readlin : list
        Readlines list object

    Returns
    -------
    geos : list
        List of all atom symbols and cartesian coordinates.
    frag_ids : dict
        Dictionary with the indices of each fragment.
    """
    sep = []
    frag = 0
    geos = []
    frag_ids = {}
    catom = 0
    # First find the limits
    for line in readlin[n+2:]:
        if "--" in line:
            frag += 1
            frag_ids[frag] = []
        elif "$end" in line:
            break
        elif len(line.split()) < 4:
            continue
        else:
            frag_ids[frag].append(catom)
            data = line.split()
            geos.append([data[0]] + list(map(float, data[1:])))
            catom += 1
    return geos, frag_ids


def parse_simple_matrix(n, readlin, stop_signals=None, asmatrix=False):
    """Parse a symmetric matrix printed columnwise

    Parameters
    ----------
    n : int
        Line number of identifier
    readlin : list
        Readlines list object
    asmatrix : bool
        Whether to return a numpy.matrix object or not

    Returns
    -------
    numpy.matrix
        Parsed AO matrix as numpy.matrix object if asmatrix=True
    list
        Parsed AO matrix as list of lists if asmatrix=False
    """
    matrix = []
    cols = 0
    index_line = n+1
    if stop_signals is None:
        stop_signals = ["Gap", "=", "eV", "Convergence", "criterion"]
    stop = 0
    for iline, line in enumerate(readlin[index_line:]):
        if any(stop in line for stop in stop_signals):
            break
        matrix.append(extract_floats(line))
    if asmatrix:  # return np.matrix object
        return np.asmatrix(matrix)
    else:  # return list of lists
        return matrix


def parse_qchem(fname, hooks, to_file=True, json_file='CCParser.json', overwrite_vals=True):
    """Parse the QChem file for a list of hooks

    Parameters
    ---------
    fname : str
        Name of file to be parsed
    hooks : dict
        Dictionary with the following info:
        type of data ('matrix', 'vector', 'number'),
        hook_string ('Dipone moment')
        args [optional]: (line_shift, position in line)
    to_file : bool
        Whether it needs to be writen to file.
    output : str
        Name of file where to save the parsed data.
    """
    with open(fname, 'r') as ifile:
        lines = ifile.readlines()
    if not isinstance(hooks, dict):
        raise TypeError("`hooks` should be given as a dictionary.")
    parsed = {}
    for n, line in enumerate(lines):
        for key in hooks:
            args = None
            if len(hooks[key]) == 2:
                otype, hook = hooks[key]
            else:
                otype, hook, args = hooks[key]
            hook = re.compile(hook)
            match = hook.search(line)
            if match:
                # Get value(s)
                if otype == 'geometry':
                    out, frag_ids = parse_molecule(n, lines)
                    parsed['frag_ids'] = [[frag_ids, n]]
                elif otype == 'simple matrix':
                    if args:
                        out = parse_simple_matrix(n, lines, **args)
                    else:
                        out = parse_simple_matrix(n, lines)
                elif otype == 'symmetric matrix':
                    out = parse_symmetric_matrix(n, lines, asmatrix=False)
                elif otype == 'vector':
#                    out = parse_inline_vec(line)
                    print("not implemented yet")
                elif otype == 'number':
                    if args:
                        out = parse_number_qchem(n, lines, **args)
                    else:
                        out = parse_number_qchem(n, lines)
                else:
                    raise NotImplementedError('Only matrices and numbers can be parsed.')
                # Save them in dictionary
                if key in parsed:
                    parsed[key].append([out, n])
                else:
                    parsed[key] = [[out, n]]
    if to_file:
        json_filepath = os.path.join(os.path.split(fname)[0],json_file) 
        # Check if file exists and update dictionary
        if os.path.isfile(json_filepath):
            parsed = update_json_dict(json_filepath, parsed, overwrite_vals)
        # Save json TODO: replace with dump_js
        with open(json_filepath, 'w') as ofile:
            json.dump(parsed, ofile)
    return parsed


def update_json_dict(json_file, parsed, overwrite_vals):
    """Update existing dictionary.

    Parameters
    ----------
    json_file : str
        File name of the json file.
    parsed :  dict
        Dictionary with data freshly parsed.
    overwrite_vals : bool
        Whether to overwrite existing values or keep previous.

    Returns
    -------
    updated : dict
        Updated dictionary
    """
    # Read json TODO: replace with load_js
    with open(json_file, 'r') as ifile:
        updated = json.load(ifile)
    if overwrite_vals:
        updated.update(parsed)
    else:
        for key in parsed:
            if key not in updated:
                updated[key] = parsed[key]
    return updated


def parse_number_qchem(n, lines, line_shift=0, position=-1):
    """Parse the the number from the line.

    Parameters
    ----------
    n : int
        Number of the line where the hook starts.
    lines : str
        Lines from text that contains the number.
    line_shift : int
        Number of lines that need to be shift to start reading.
    position : int
        From the splitted line, which position occupies
        the requiered number, default assumes the last part.

    Returns
    -------
    number : int or float

    """
    number = lines[n+line_shift].split()[position]
    try:
        number = int(number)
    except ValueError:
        number = float(number)
    return number
 
###########################################################################
# The hooks
# Each hook contains: (type, hook_string, extra_args)
# type: could be 'matrix', 'vector', 'number'
hooks = {"scf_energy" : ("number", "SCF   energy in the final basis set"),
         "overlap_matrix" : ("matrix", " Overlap Matrix"),
         "mp_energy": ("number", r"(RI-)?MP\([2-3]\) Summary", dict(line_shift=3, position=2)),
         "exc_energies": ("number", "Excitation energy:", dict(position=-2)),
         "osc_strength": ("number", "Osc. strength:"),
         "total_dipole" : ("number", "Total dipole"),
         "xyz": ('geometry', r"\$molecule"),
         "EFG_tensor_e": ('simple matrix', r"^  Raw EFG tensor \(electronic", dict(stop_signals=['Raw', ' EFG'])),
         "EFG_tensor_n": ('simple matrix', r"^  Raw EFG tensor \(nuclear", dict(stop_signals=['Raw', ' EFG'])),
         "EFG_tensor_t": ('simple matrix', r"^  Raw EFG tensor \(total", dict(stop_signals=['Principal'])),
        }


#if __name__ == "__main__":
#    fname = 'emb1.out'
#    parse_qchem(fname, hooks, to_file=True)
