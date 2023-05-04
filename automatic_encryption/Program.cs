﻿using MongoDB.Bson;
using MongoDB.Driver;
using MongoDB.Driver.Encryption;
using System.Security.Cryptography.X509Certificates;

// IN VALUES HERE!
const string PETNAME = "solid-cat";
const string MDB_PASSWORD = "password123";

const string AppUser = "app_user";
const string CaPath = "/etc/pki/tls/certs/ca.cert";

// Note that the .NET driver requires the certificate to be in PKCS12 format. You can convert
// the file /home/ec2-user/server.pem into PKCS12 with the command
// openssl pkcs12 -export -out "/home/ec2-user/server.pkcs12" -in "/home/ec2-user/server.pem" -name "kmipcert"
const string Pkcs12Path = "/home/ec2-user/server.pkcs12";

// Obviously this should not be hardcoded
const string connectionString = $"mongodb://{AppUser}:{MDB_PASSWORD}@csfle-mongodb-{PETNAME}.mdbtraining.net/?serverSelectionTimeoutMS=5000&tls=true&tlsCAFile={CaPath}";

// Declare our key vault namespce
const string keyvaultDb = "__encryption";
const string keyvaultColl = "__keyVault";
var keyvaultNamespace = new CollectionNamespace(keyvaultDb, keyvaultColl);

// Declare our key provider type
const string provider = "kmip";

// Declare our key provider attributes
var providerSettings = new Dictionary<string, object>
{
    { "endpoint", $"csfle-kmip-{PETNAME}.mdbtraining.net" }
};
var kmsProvider = new Dictionary<string, IReadOnlyDictionary<string, object>>
{
    { provider, providerSettings }
};

// Declare our database and collection
const string encryptedDbName = "companyData";
const string encryptedCollName = "employee";

// Instantiate our MongoDB Client object
var client = MdbClient(connectionString);

// Retrieve the DEK UUID
var filter = Builders<BsonDocument>.Filter.Eq(d => d["keyAltNames"], "dataKey1");
var dataKeyId_1 = (await (await client.GetDatabase(keyvaultDb).GetCollection<BsonDocument>(keyvaultColl).FindAsync(filter)).FirstOrDefaultAsync<BsonDocument>())["_id"];
if (dataKeyId_1.IsBsonNull)
{
    Console.WriteLine("Failed to find DEK");
    return;
}

var schema = new BsonDocument
{
    { "bsonType", "object" },
    {
        "encryptMetadata", new BsonDocument {
            { "keyId", new BsonArray { dataKeyId_1 } },
            { "algorithm", "AEAD_AES_256_CBC_HMAC_SHA_512-Random" }
        }
    },
    {
        "properties", new BsonDocument { {
            "name", new BsonDocument {
                { "bsonType", "object"} ,
                {
                    "properties", new BsonDocument { {
                        "firstName", new BsonDocument { {
                            "encrypt", new BsonDocument {
                                { "bsonType", "string" },
                                { "algorithm", "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic" }
                            }
                        } }
                    },
                    {
                        "lastName", new BsonDocument { {
                            "encrypt", new BsonDocument {
                                { "bsonType", "string" },
                                { "algorithm", "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic" }
                            }
                        } }
                    },
                    {
                        "otherNames", new BsonDocument { {
                            "encrypt", new BsonDocument { { "bsonType", "string" } }
                        } }
                    } }
                } }
            },
            {
                "address", new BsonDocument { {
                    "encrypt", new BsonDocument { { "bsonType", "object" } }
                } }
            },
            {
                "dob", new BsonDocument { {
                    "encrypt", new BsonDocument { { "bsonType", "date" } }
                } }
            },
            {
                "phoneNumber", new BsonDocument { {
                    "encrypt", new BsonDocument { { "bsonType", "string" } }
                } }
            },
            {
                "salary", new BsonDocument { {
                    "encrypt", new BsonDocument { { "bsonType", "double" } }
                } }
            },
            {
                "taxIdentifier", new BsonDocument { {
                    "encrypt", new BsonDocument { { "bsonType", "string" } }
                } }
            }
        }
    }
};
var schemaMap = new Dictionary<string, BsonDocument> { {"companyData.employee", schema } };

var tlsOptions = new SslSettings { ClientCertificates = new[] { new X509Certificate(Pkcs12Path) } };
var kmsTlsOptions = new Dictionary<string, SslSettings> { { provider, tlsOptions } };
var extraOptions = new Dictionary<string, object>()
{
    { "cryptSharedLibPath", "/lib/mongo_crypt_v1.so"},
    { "cryptSharedLibRequired", true },
    { "mongocryptdBypassSpawn", true }
};
var autoEncryption = new AutoEncryptionOptions(
    kmsProviders: kmsProvider,
    keyVaultNamespace: keyvaultNamespace,
    schemaMap: schemaMap,
    extraOptions: extraOptions,
    tlsOptions: kmsTlsOptions);

var encryptedClient = MdbClient(connectionString, autoEncryption);

Console.WriteLine("Enter firstName:");
var firstName = "Magnus";// Console.ReadLine();
Console.WriteLine("Enter lastName:");
var lastName = "Stråle";//Console.ReadLine();

var payload = new BsonDocument
{
    {
        "name", new BsonDocument
        {
            { "firstName", firstName },
            { "lastName", lastName },
            { "otherNames", BsonNull.Value },
        }
    },
    {
        "address", new BsonDocument
        {
            { "streetAddress", "29 Bson Street" },
            { "suburbCounty", "Mongoville" },
            { "stateProvince", "Victoria" },
            { "zipPostcode", "3999" },
            { "country", "Oz" }
        }
    },
    { "dob", new DateTime(1999, 1, 12) },
    { "phoneNumber", "1800MONGO" },
    { "salary", 999999.99 },
    { "taxIdentifier", "78SDSSWN001" },
    { "role", new BsonArray { "CE" } }
};

// Do deterministic fields
if (payload["name"]["otherNames"].IsBsonNull)
{
    payload["name"].AsBsonDocument.Remove("otherNames");
}

await encryptedClient.GetDatabase(encryptedDbName).GetCollection<BsonDocument>(encryptedCollName).InsertOneAsync(payload);
Console.WriteLine(payload["_id"]);

static MongoClient MdbClient(string connectionString, AutoEncryptionOptions? options = null)
{
    var settings = MongoClientSettings.FromConnectionString(connectionString);
    if (options != null) settings.AutoEncryptionOptions = options;

    return new MongoClient(settings);
}