from .logger import Logger
import pandas
import sqlite3
from sqlite3 import Error

log = Logger('__main__')

class DB_Manager:

    def __init__(self):
        self.connection = None

    def create_connection(self, db_path):
        # Create a database connection to a SQLite database
        try:
            self.connection = sqlite3.connect(db_path)  # creates a SQL database in the 'data' directory
            log.info("Successfully connected to the database.")
        except Error as e:
            log.error(f"Error thrown while attempting to connect to database, error: {e}")
            self.connection = None
        return self.connection

    def close(self):
        if self.connection:
            try:
                self.connection.close()
                log.info("Database connection closed.")
            except sqlite3.Error as e:
                log.error(f"Error closing the database connection: {e}")

    def create_table(self, df, table_name):
        ''''
        # Create a new table with the data from the dataframe
        df.to_sql(table_name, connection, if_exists='replace', index=False)
        print (f"Created the {table_name} table and added {len(df)} records")
        '''
        # Create a new table with the data from the DataFrame
        # Prepare data types mapping from pandas to SQLite
        type_mapping = {
            'int64': 'INTEGER',
            'float64': 'REAL',
            'datetime64[ns]': 'TIMESTAMP',
            'object': 'TEXT',
            'bool': 'INTEGER'
        }

        # Prepare a string with column names and their types
        columns_with_types = ', '.join(
            f'"{column}" {type_mapping[str(df.dtypes[column])]}'
            for column in df.columns
        )

        # Prepare SQL query to create a new table
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {columns_with_types}
            );
        """

        # Execute SQL query
        cursor = self.connection.cursor()
        cursor.execute(create_table_sql)

        # Commit the transaction
        self.connection.commit()

        # Insert DataFrame records one by one
        insert_sql = f"""
            INSERT INTO "{table_name}" ({', '.join(f'"{column}"' for column in df.columns)})
            VALUES ({', '.join(['?' for _ in df.columns])})
        """
        for record in df.to_dict(orient='records'):
            cursor.execute(insert_sql, list(record.values()))

        # Commit the transaction
        self.connection.commit()

        log.info(f"Created the {table_name} table and added {len(df)} records")

    def update_table(self, df, table_name):
        # Update the existing table with new records.
        df_existing = pandas.read_sql(f'select * from {table_name}', self.connection)

        # Create a dataframe with unique records in df that are not in df_existing
        df_new_records = (pandas.concat([df, df_existing, df_existing])
                          .drop_duplicates(['title', 'company', 'date'], keep=False))

        # If there are new records, append them to the existing table
        if len(df_new_records) > 0:
            df_new_records.to_sql(table_name, self.connection, if_exists='append', index=False)
            log.info(f"Added {len(df_new_records)} new records to the {table_name} table")
        else:
            log.info(f"No new records to add to the {table_name} table")

    def table_exists(self, table_name):
        # Check if the table already exists in the database
        cur = self.connection.cursor()
        cur.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cur.fetchone()[0] == 1:
            return True
        return False

    def find_new_jobs(self, all_jobs, config):
        # From all_jobs, find the jobs that are not already in the database. Function checks both the jobs and filtered_jobs tables.
        jobs_tablename = config['jobs_tablename']
        filtered_jobs_tablename = config['filtered_jobs_tablename']
        jobs_db = pandas.DataFrame()
        filtered_jobs_db = pandas.DataFrame()
        if self.connection is not None:
            if self.table_exists(jobs_tablename):
                query = f"SELECT * FROM {jobs_tablename}"
                jobs_db = pandas.read_sql_query(query, self.connection)
            if self.table_exists(filtered_jobs_tablename):
                query = f"SELECT * FROM {filtered_jobs_tablename}"
                filtered_jobs_db = pandas.read_sql_query(query, self.connection)

        new_joblist = [job for job in all_jobs if not self.job_exists(jobs_db, job)
                       and not self.job_exists(filtered_jobs_db, job)]
        return new_joblist

    def job_exists(self, df, job):
        # Check if the job already exists in the dataframe
        if df.empty:
            return False
        #return ((df['title'] == job['title']) & (df['company'] == job['company']) & (df['date'] == job['date'])).any()
        #The job exists if there's already a job in the database that has the same URL
        return ((df['job_url'] == job['job_url']).any() | (
            ((df['title'] == job['title']) & (df['company'] == job['company']) & (df['date'] == job['date'])).any()))