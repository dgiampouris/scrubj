import gcc
import re
import zmq
import time
import pickle

# Creates a zmq context and the sockets needed
def connect():
    context = zmq.Context()

    # Socket to establish connection with client
    publisher = context.socket(zmq.PUB)
    publisher.bind("ipc:///tmp/feeds/0")
    # Set SNDHWM, in case of slow subscribers
    publisher.sndhwm = 1100000
    time.sleep(0.2)

    return publisher


# Replaces the temporary variables in the gimple statements
def unfold(tvars, temp_var):
    restr1 = r'[A-Z]\.\w+'
    restr2 = r'_[0-9]+'
    rexp1 = re.compile(restr1)
    rexp2 = re.compile(restr2)

    try:
        argument = tvars["'" + temp_var + "'"]
    except KeyError:
        return 'Error_arg'

    while True:
        m1 = rexp1.search(argument) # Here is the prob
        m2 = rexp2.search(argument)

        if(m1 == None and m2 == None):
            break

        if m1:
            temp_var = m1.group()
        if m2:
            temp_var = m2.group()

        try:
            if m1:
                argument = rexp1.sub(tvars["'" + temp_var + "'"], argument)
            if m2:
                argument = rexp2.sub(tvars["'" + temp_var + "'"], argument)
        except KeyError:
            argument = 'Error_arg'

    return argument


# Makes a dictionary with all the gimple statements UIDs
def intake(stmt, tvars):
    restr1 = r'(^[A-Z]\.\w+)(\s=\s)([^;]*)' # group(1) = UID, group(3) = stmt
    restr2 = r'(^_[0-9]+)(\s=\s)([^;]*)' # group(1) = _, group(3) = stmt
    rexp1 = re.compile(restr1)
    rexp2 = re.compile(restr2)

    m1 = rexp1.search(str(stmt))
    m2 = rexp2.search(str(stmt))
    if m1:
        tvars["'" + m1.group(1) + "'"] = m1.group(3)

    if m2:
        tvars["'" + m2.group(1) + "'"] = m2.group(3)

    return tvars


def on_pass_execution(p, fn):
    if p.name == '*free_lang_data':
        global publisher
        fname = ""
        arguments = {}
        tvars = {}
        data = {}
        callees_list = []
        callers_list = []
        parent_types_list = []
        restr1 = r'[A-Z]\.[0-9]+'
        restr2 = r'_[0-9]+'
        rexp1 = re.compile(restr1)
        rexp2 = re.compile(restr2)



        for node in gcc.get_callgraph_nodes():

            try:
                fn = node.decl.function
                cl = node.callees
                cr = node.callers

                parent = str(fn.decl.name) + '@' + str(fn.decl.location.file) \
                        + '_L' + str(fn.decl.location.line) + '_C' \
                        + str(fn.decl.location.column)
                data['parent'] = parent

                parent_type = str(fn.decl.type.type)
                data['parent_type'] = parent_type

                for edge in cl:
                    callees_list.append(str(edge.call_stmt.fn) + '@' \
                            + str(edge.call_stmt.loc.file) + '_L' \
                            + str(edge.call_stmt.loc.line) + '_C' \
                            + str(edge.call_stmt.loc.column))
                data['callees'] = callees_list

                for edge in cr:
                    callers_list.append(str(edge.caller.decl.name) + '@' \
                            + str(edge.caller.decl.location.file) + '_L' \
                            + str(edge.caller.decl.location.line) + '_C' \
                            + str(edge.caller.decl.location.column))
                data['callers'] = callers_list

                for arg in fn.decl.type.argument_types:
                    parent_types_list.append(str(arg))

                data['parent_argument_types'] = parent_types_list
            except AttributeError:
                continue

            """
            print("IN FUNCTION:")
            print(parent)
            print("WHICH TYPE IS:")
            print(parent_type)
            print('AND ITS ARGUMENT\'S TYPES ARE: %r' \
                    % [str(arg) for arg in fn.decl.type.argument_types])
            print("THAT CALLS:")
            print(callees_list)
            print("AND IS CALLED BY")
            print(callers_list)
            print("ALL FUNCTION CALLS")
            """


            try:
                for bb in fn.cfg.basic_blocks:
                    for stmt in bb.gimple:
                        tvars = intake(stmt, tvars)
                        if isinstance(stmt, gcc.GimpleCall):
                            fnmatch1 = rexp1.search(str(stmt.fn))
                            fnmatch2 = rexp2.search(str(stmt.fn))

                            if fnmatch1:
                                fname = str(unfold(tvars, fnmatch1.group())) \
                                        + '@' + str(stmt.loc.file) \
                                        + '_L' + str(stmt.loc.line) + '_C' \
                                        + str(stmt.loc.column)
                                #print(fname)
                            elif fnmatch2:
                                fname = str(unfold(tvars, fnmatch2.group())) \
                                        + '@' + str(stmt.loc.file) \
                                        + '_L' + str(stmt.loc.line) + '_C' \
                                        + str(stmt.loc.column)
                                #print(fname)
                            else:
                                fname = str(stmt.fn) + '@' + str(stmt.loc.file) \
                                        + '_L' + str(stmt.loc.line) + '_C' \
                                        + str(stmt.loc.column)
                                #print(fname)

                            for i, arg in enumerate(stmt.args):
                                m1 = rexp1.search(str(stmt.args[i]))
                                m2 = rexp2.search(str(stmt.args[i]))
                                if m1:
                                    arguments[i] = unfold(tvars, m1.group())
                                elif m2:
                                    arguments[i] = unfold(tvars, m2.group())
                                else:
                                    arguments[i] = str(stmt.args[i])
                            #print(arguments)
                            data[fname] = arguments
                            arguments = {}

                #print("----------------------------------")
            except AttributeError:
                continue


            data_string = pickle.dumps(data)
            publisher.send(data_string)
            data.clear()
            del callees_list[:]
            del callers_list[:]
            del parent_types_list[:]

            #pprint.pprint(tvars)

    if p.name == "ssa":
        publisher.send(b"GCC_DISCONNECT")



publisher = connect()
gcc.register_callback(gcc.PLUGIN_PASS_EXECUTION, on_pass_execution)
