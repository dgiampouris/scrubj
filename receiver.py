import pickle
import zmq
import pprint
import re
from neo4j import GraphDatabase


# Neo4j Functions

def dbhandle(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    return driver

def dbclose(driver):
    driver.close()

def create_project(driver, project_name):
    with driver.session() as session:
        tx = session.begin_transaction()
        create_project_node(tx, project_name)
        tx.commit()

def create_project_node(tx, project_name):
    tx.run("CREATE (p:project {name:{project_name}})",
            project_name=project_name)


def create_node(driver, loc, fname, ftype, argument_types, project_name):
    with driver.session() as session:
        tx = session.begin_transaction()
        create_function_node(tx, loc, fname, ftype, argument_types, project_name)
        tx.commit()


def create_function_node(tx, loc, fname, ftype, argument_types, project_name):
    tx.run("MERGE (n:function:parent {loc:{loc}, name:{fname}}) \
            ON CREATE SET n.type = {ftype}, \
            n.argument_types = {argument_types} \
            ON MATCH SET n.type = {ftype}, \
            n.argument_types = {argument_types} \
            WITH n \
            MATCH (n:function:parent), (p:project) \
            WHERE n.name={fname} AND p.name={project_name} \
            MERGE (n)-[r:IN_PROJECT]->(p)", loc=loc,
            fname=fname, ftype=ftype, argument_types=argument_types,
            project_name=project_name)



def create_callee_node(driver, loc, fname, parent_name, parent_loc, arg_list, project_name):
    with driver.session() as session:
        tx = session.begin_transaction()
        create_callee_function(tx, loc, fname, parent_name, parent_loc, arg_list, project_name)
        tx.commit()

def create_callee_function(tx, loc, fname, parent_name, parent_loc, arg_list, project_name):
    tx.run("MATCH (f:function:parent) \
            WHERE f.name={parent_name} AND f.loc={parent_loc} \
            MERGE (n:function:callee {loc:{loc}, name:{fname}}) \
            WITH n \
            MATCH (n:function:callee), (p:project) \
            WHERE n.name={fname} AND p.name={project_name} \
            MERGE (n)-[r:IN_PROJECT]->(p) \
            WITH n \
            MATCH (f:function:parent),(n:function:callee) \
            WHERE f.name={parent_name} AND n.name={fname} \
            MERGE (f)-[r:CALLS {arguments:{arg_list}}]->(n)",
            parent_name=parent_name, parent_loc=parent_loc, loc=loc,
            fname=fname, arg_list=arg_list, project_name=project_name)


"""
def create_caller_edge(driver, loc, fname, callee_name, callee_loc):
    with driver.session() as session:
        tx = session.begin_transaction()
        create_caller_function(tx, loc, fname, callee_name, callee_loc)
        tx.commit()


def create_caller_function(tx, loc, fname, callee_name, callee_loc):
    tx.run("MATCH (f:function) WHERE f.name={callee_name} AND f.loc={callee_loc} \
            MATCH (n:function) WHERE n.name={fname} AND n.loc={loc} \
            CREATE (n)-[:IS_CALLED_BY]->(f)",
            callee_name=callee_name, callee_loc=callee_loc, loc=loc, fname=fname)
"""

# Zeromq PUB-SUB functions
def connect():
    context = zmq.Context()

    # Connect the subscriber socket
    subscriber = context.socket(zmq.SUB)
    subscriber.connect('ipc:///tmp/feeds/0')
    subscriber.setsockopt(zmq.SUBSCRIBE, b'')

    return subscriber

# Where it all goes down
def main():
    subscriber = connect()
    count = 0
    gcc_disconnect = False
    arg_list = []
    master = {}
    restr = r'(.+)(\@)(.+)'
    rexp = re.compile(restr)

    # TODO: Add here project name input and add it in the db nodes
    project_name = input("Enter the project name: ")


    while True:
        try:
            msg = subscriber.recv()
            if msg == b"GCC_DISCONNECT":
                if gcc_disconnect == False: # When ms pass without receive
                    subscriber.RCVTIMEO = 300000 # the conn will close
                    gcc_disconnect = True # find alternative when possible
                else:
                    continue
            else:
                data = pickle.loads(msg)
                master[count] = data
                pprint.pprint(master[count])
                #data.clear()
                count += 1

        except zmq.error.Again:
            print("gcc disconnected")
            break
        except KeyboardInterrupt:
            print("Interrupt received, stopping...")
            break

    # Add your uri, user and password
    db = dbhandle("bolt://192.168.56.101:7687", "neo4j", "password")

    # Create project node
    create_project(db, project_name)

    for key in master:
        temp = master[key]
        m1 = rexp.search(str(temp['parent']))
        #print(str(m.group(3))) this is the loc
        #print(str(m.group(1))) this is the fname
        #print(str(temp['parent_type']))

        if m1:
            create_node(db, str(m1.group(3)), str(m1.group(1)),
                str(temp['parent_type']), str(temp['parent_argument_types']),
                project_name)


        for callee in temp['callees']:
            m2 = rexp.search(str(callee))

            try:
                for arg in temp[callee].values():
                    arg_list.append(arg)
            except KeyError:
                arg_list.append("no_args")


            if m2:
                create_callee_node(db, str(m2.group(3)), str(m2.group(1)),
                        str(m1.group(1)), str(m1.group(3)),
                        arg_list, project_name)
                del arg_list[:]


        """

        for caller in temp['callers']:
            m3 = rexp.search(str(callee))

            if m3:
                create_caller_edge(db, str(m3.group(3)), str(m3.group(1)),
                        str(m1.group(1)), str(m1.group(3)))

        """


    dbclose(db)


if __name__ == "__main__":
    main()
