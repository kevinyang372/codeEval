from flask_login import current_user
from flask import redirect, url_for, flash, request, jsonify
from functools import wraps
from web import app
import os
import nbformat
from nbconvert import PythonExporter
import pygments
from web.models import User, Result
import json
import itertools
import ast
from zss import simple_distance, Node


def is_valid(filename):
    """Validate user uploaded files' filename"""
    if filename and '.' in filename and filename.split('.')[1] in app.config["ALLOWED_EXTENSIONS"]:
        return True
    return False


def read_file(file, filename):
    """Read user uploaded files"""

    file.save(os.path.join(app.config["FILE_UPLOADS"], filename))

    content = []
    with open(os.path.join(app.config["FILE_UPLOADS"], filename), 'r') as file:
        for line in file:
            content.append(line)

    os.remove(os.path.join(app.config["FILE_UPLOADS"], filename))
    return ''.join(content)


def admin_required(f):
    """Decorator for requiring admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user or not current_user.is_admin:
            flash('You have no access to this page')
            return redirect(url_for('index.index'))
        return f(*args, **kwargs)
    return decorated_function


def user_required_api(f):
    """Decorator for requiring user access in api"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        
        if request.json:
            email = str(request.json['credentials']['email'])
            password = str(request.json['credentials']['password'])
        elif request.form:
            email = str(request.form['email'])
            password = str(request.form['password'])

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            return jsonify(data={'message': 'Fails to verify user credentials'})
        return f(*args, **kwargs)
    return decorated_function


def admin_required_api(f):
    """Decorator for requiring admin access in api"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        email = str(request.json['credentials']['email'])
        password = str(request.json['credentials']['password'])

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password) or not user.is_admin:
            return jsonify(data={'message': 'Fails to verify user credentials'})
        return f(*args, **kwargs)
    return decorated_function

def convert_jupyter(file, filename):
    """Read jupyter notebook uploads"""

    file.save(os.path.join(app.config["FILE_UPLOADS"], filename))

    with open(os.path.join(app.config["FILE_UPLOADS"], filename)) as f:
        nb = nbformat.reads(f.read(), nbformat.NO_CONVERT)

    exporter = PythonExporter()
    source, _ = exporter.from_notebook_node(nb)

    os.remove(os.path.join(app.config["FILE_UPLOADS"], filename))
    return source


def highlight_python(code):
    """highlight python code to html"""

    formatter = pygments.formatters.HtmlFormatter(style="emacs", cssclass="codehilite")
    css_string = "<style>" + formatter.get_style_defs() + "</style>"

    return css_string + pygments.highlight(code, pygments.lexers.PythonLexer(), formatter)


def compile_results(res):
    """compile results into models"""

    compiled = {}
    for question in res:
        compiled[question] = {}

        compiled[question]['total_num'] = len(res[question])
        compiled[question]['passed_num'] = sum([1 for case in res[question] if res[question][case] == "Passed"])
        compiled[question]['reason'] = res[question]

    return compiled


def compile_plagarism_report(code, user_id, session_id):

    results = Result.query.filter(Result.user_id != user_id, Result.session_id == session_id).all()
    tree1 = ast.parse(code)
    res = []

    for result in results:
        tree2 = ast.parse(result.content)

        comparison = [0] * 5
        comparison[0] = 1 if exact_match(tree1, tree2) else 0
        comparison[1] = 1 if unifying_ast_match(tree1, tree2) else 0
        comparison[2] = 1 if ast_match_ignoring_variables(tree1, tree2) else 0
        comparison[3] = 1 if ast_match_reordering(tree1, tree2) else 0
        comparison[4] = simple_distance((copyTree(tree1, None)), (copyTree(tree2, None)))

        res.append({'result': comparison, 'result_id': result.id})

    return res


# Exact match between two pieces of code
def exact_match(node1, node2):
    if type(node1) is not type(node2):
        return False
    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ('lineno', 'col_offset', 'ctx'):
                continue
            if not exact_match(v, getattr(node2, k)):
                return False

        return True
    elif isinstance(node1, list):
        return all(itertools.starmap(exact_match, zip(node1, node2)))
    else:
        return node1 == node2


# unifying ast match detecting naive variable renaming
def unifying_ast_match(node1, node2):
    if type(node1) is not type(node2):
        return False
    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ('lineno', 'col_offset', 'ctx'):
                continue

            if (k == 'id' or k == 'arg') and v != getattr(node2, k):
                if v not in mapping:
                    mapping[v] = getattr(node2, k)
                elif mapping[v] != getattr(node2, k):
                    return False
            elif not unifying_ast_match(v, getattr(node2, k)):
                return False

        return True
    elif isinstance(node1, list):
        return all(itertools.starmap(unifying_ast_match, zip(node1, node2)))
    else:
        return node1 == node2


# ignore variables
def ast_match_ignoring_variables(node1, node2):
    if type(node1) is not type(node2):
        return False
    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ('lineno', 'col_offset', 'ctx', 'id', 'arg'):
                continue
            elif not ast_match_ignoring_variables(v, getattr(node2, k)):
                return False

        return True
    elif isinstance(node1, list):
        return all(itertools.starmap(ast_match_ignoring_variables, zip(node1, node2)))
    else:
        return node1 == node2


# reordering
def ast_match_reordering(node1, node2):
    if type(node1) is not type(node2):
        return False
    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ('lineno', 'col_offset', 'ctx', 'id', 'arg'):
                continue
            elif not ast_match_reordering(v, getattr(node2, k)):
                return False

        return True
    elif isinstance(node1, list):
        if len(node1) != len(node2): return False
        return any(all(itertools.starmap(ast_match_reordering, zip(node1, i))) for i in itertools.permutations(node2))
    else:
        return node1 == node2

def copyTree(node, dummy):
    t = type(node).__name__

    if 'name' in node._fields:
        t += ':' + node.name
    elif 'id' in node._fields:
        t += ':' + node.id
    
    curr = Node(t)
    if dummy is not None: dummy.addkid(curr)

    for k, v in vars(node).items():
        if isinstance(v, list):
            for p in v:
                if isinstance(p, ast.AST):
                    copyTree(p, curr)
        elif isinstance(v, ast.AST):
            copyTree(v, curr)

    return curr