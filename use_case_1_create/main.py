# CSFLE Use Case skeleton code
import sys
import names
from pymongo.errors import EncryptionError, ServerSelectionTimeoutError, ConnectionFailure
from bson.codec_options import CodecOptions
from pymongo.encryption_options import AutoEncryptionOpts
from pymongo.encryption import ClientEncryption
from bson.binary import STANDARD, Binary
from pymongo import MongoClient
from pprint import pprint
from datetime import datetime
from random import randint

# IN VALUES HERE!
PETNAME = 
MDB_PASSWORD = 

# create our MongoClient with the required attributes, and test the connection
def mdb_client(db_data, auto_encryption_opts=None):
  try:
    client = MongoClient(db_data['DB_CONNECTION_STRING'], serverSelectionTimeoutMS=db_data['DB_TIMEOUT'], tls=True, tlsCAFile=db_data['DB_SSL_CA'], auto_encryption_opts=auto_encryption_opts)
    client.admin.command('hello')
    return client, None
  except (ServerSelectionTimeoutError, ConnectionFailure) as e:
    return None, f"Cannot connect to database, please check settings in config file: {e}"

def get_employee_key(client, altName, provider_name, keyId):
  employee_key_id = client.get_key_by_alt_name(str(altName))
  if employee_key_id == None:
    try:
      #PUT CODE HERE TO CREATE THE NEW DEK
      master_key = 
      employee_key_id = 
    except EncryptionError as e:
      return None, f"ClientEncryption error: {e}"
  else:
    employee_key_id = employee_key_id["_id"]
  return employee_key_id, None

def main():

  # Obviously this should not be hardcoded
  config_data = {
    "DB_CONNECTION_STRING": f"mongodb://app_user:{MDB_PASSWORD}@csfle-mongodb-{PETNAME}.mdbtraining.net",
    "DB_TIMEOUT": 5000,
    "DB_SSL_CA": "/etc/pki/tls/certs/ca.cert"
  }

  # Declare or key vault namespce
  keyvault_db = "__encryption"
  keyvault_coll = "__keyVault"
  keyvault_namespace = f"{keyvault_db}.{keyvault_coll}"

  # declare our key provider type
  provider = "kmip"

  # declare our key provider attributes
  kms_provider = {
    provider: {
      "endpoint": f"csfle-kmip-{PETNAME}.mdbtraining.net"
    }
  }
  
  # declare our database and collection
  encrypted_db_name = "companyData"
  encrypted_coll_name = "employee"

  # instantiate our MongoDB Client object
  client, err = mdb_client(config_data)
  if err != None:
    print(err)
    sys.exit(1)

  # Create ClientEncryption instance for creating DEks and manual encryption
  client_encryption = ClientEncryption(
    kms_provider,
    keyvault_namespace,
    client,
    CodecOptions(uuid_representation=STANDARD),
    kms_tls_options = {
      "kmip": {
        "tlsCAFile": "/etc/pki/tls/certs/ca.cert",
        "tlsCertificateKeyFile": "/home/ec2-user/server.pem"
      }
    }
  )

  employee_id = str("%05d" % randint(0,99999))
  firstname = names.get_first_name()
  lastname = names.get_last_name()

  # retrieve the DEK UUID
  employee_key_id, err = get_employee_key(client_encryption, employee_id, provider, '1')
  if err != None:
    print(err)
    sys.exit(1)

  payload = {
    "_id": employee_id, # we are using this as out keyAltName
    "name": {
      "firstName": "",
      "lastName": "",
      "otherNames": None,
    },
    "address": {
      "streetAddress": "3 Bson Street",
      "suburbCounty": "Mongoville",
      "stateProvince": "Victoria",
      "zipPostcode": "3999",
      "country": "Oz"
    },
    "dob": datetime(1978, 10, 10),
    "phoneNumber": "1800MONGO",
    "salary": 999999.99,
    "taxIdentifier": "78SD20NN001",
    "role": [
      "CIO"
    ]
  }
  
  encrypted_db_name = "companyData"
  encrypted_coll_name = "employee"
  schema_map = {
    "companyData.employee": {
      "bsonType": "object",
      "encryptMeta": {
        "keyId": , # PUT APPROPRIATE CODE OR VARIABLE HERE
        "algorithm": "AEAD_AES_256_CBC_HMAC_SHA_512_Random"
      },
      "properties": {
        "name": {
          "bsonType": "object",
          "properties": {
            "otherNames": {
              "encrypt" : {
                "bsonType": "string"
              }
            }
          }
        },
        "address": {
          "encrypt": {
            "bsonType": "object"
          }
        },
        "dob": {
          "encrypt": {
            "bsonType": "datetime"
          }
        },
        "phoneNumber": {
          "encrypt": {
            "bsonType": "string"
          }
        },
        "salary": {
          "encrypt": {
            "bsonType": "double"
          }
        },
        "taxIdentifier": {
          "encrypt": {
            "bsonType": "string"
          }
        }
      }
    }
  }

  auto_encryption = AutoEncryptionOpts(
    kms_provider,
    keyvault_namespace,
    schema_map = schema_map,
    kms_tls_options = {
      "kmip": {
        "tlsCAFile": "/etc/pki/tls/certs/ca.cert",
        "tlsCertificateKeyFile": "/home/ec2-user/server.pem"
      }
    }
  )

  secure_client, err = mdb_client(config_data, auto_encryption_opts=auto_encryption)
  if err != None:
    print(err)
    sys.exit(1)
  encrypted_db = secure_client[encrypted_db_name]

  # ENCRYPT THE name.firstName and name.lastName here
  enc_first_name = # use the YOUR_FIRSTNAME variable
  enc_last_name = # use the YOUR_LASTNAME variable
  payload["name"]["firstName"] = enc_first_name
  payload["name"]["lastName"] = enc_last_name

  if type(payload["name"]["firstName"]) is not Binary or type(payload["name"]["lastName"]) is not Binary or payload["name"]["firstName"].subtype != 6 or payload["name"]["lastName"].subtype != 6:
    print("Data is not encrypted")
    sys.exit()

  # remove `name.otherNames` if None because wwe cannot encrypt none
  if payload["name"]["otherNames"] == None:
    del(payload["name"]["otherNames"])

  try:
    result = encrypted_db[encrypted_coll_name].insert_one(payload)
    print(result.inserted_id)
  except EncryptionError as e:
    print(f"Encryption error: {e}")
    sys.exit(1)


  try: 
    result = encrypted_db[encrypted_coll_name].find_one({"name.firstName": enc_first_name, "name.lastName": enc_last_name})
  except EncryptionError as e:
    print(f"Encryption error: {e}")
    sys.exit(1)

  pprint(result)

if __name__ == "__main__":
  main()