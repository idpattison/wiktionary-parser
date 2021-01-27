from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

url = 'neo4j+s://c1d99006.databases.neo4j.io'
user = 'neo4j'
pw = 'Qouz6eQqfIj0Ku8M70tv7AZXv5lnabWT2LkyR9o_eHA'

driver = GraphDatabase.driver(url, auth=(user, pw))

def create_tx(tx):
    query = (
        "CREATE (p1:Person { name: 'Alice' }) "
        "CREATE (p2:Person { name: 'Bob' }) "
        "CREATE (p1)-[:KNOWS]->(p2) "
        "RETURN p1, p2"
    )
    result = tx.run(query)
    return [{"p1": row["p1"]["name"], "p2": row["p2"]["name"]}
        for row in result]

with driver.session() as session:
    result = session.write_transaction(create_tx)
    print(result)
