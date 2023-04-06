package main

import (
	"C"
	"context"
	"crypto/tls"
	"fmt"
	"os"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"github.com/goombaio/namegenerator"
)

var (
	PETNAME = 
	MDB_PASSWORD =
)

func createClient(c string) (*mongo.Client, error) {
	client, err := mongo.Connect(context.TODO(), options.Client().ApplyURI(c))

	if err != nil {
		return nil, err
	}

	return client, nil
}

func createManualEncryptionClient(c *mongo.Client, kp map[string]map[string]interface{}, kns string, tlsOps map[string]*tls.Config) (*mongo.ClientEncryption, error) {
	o := options.ClientEncryption().SetKeyVaultNamespace(kns).SetKmsProviders(kp).SetTLSConfig(tlsOps)
	client, err := mongo.NewClientEncryption(c, o)
	if err != nil {
		return nil, err
	}

	return client, nil
}

func createAutoEncryptionClient(c string, ns string, kms map[string]map[string]interface{}, tlsOps map[string]*tls.Config, s bson.M) (*mongo.Client, error) {
	autoEncryptionOpts := options.AutoEncryption().
		SetKeyVaultNamespace(ns).
		SetKmsProviders(kms).
		SetSchemaMap(s).
		SetTLSConfig(tlsOps)

	client, err := mongo.Connect(context.TODO(), options.Client().ApplyURI(c).SetAutoEncryptionOptions(autoEncryptionOpts))

	if err != nil {
		return nil, err
	}

	return client, nil
}

func nameGenerator()(string, string) {
	seed := time.Now().UTC().UnixNano()
	nameGenerator := namegenerator.NewNameGenerator(seed)

	name := nameGenerator.Generate()

	firstName := strings.Split(name, "-")[0]
	lastName := strings.Split(name, "-")[1]

	return firstName, lastName
}

func main(){
	var (
		keyVaultDB 			 = "__encryption"
		keyVaultColl 		 = "__keyVault"
		keySpace         = keyVaultDB + "." + keyVaultColl
		connectionString = "mongodb://app_user:" + MDB_PASSWORD + "@csfle-mongodb-" + PETNAME + ".mdbtraining.net/?replicaSet=rs0&tls=true&tlsCAFile=%2Fetc%2Fpki%2Ftls%2Fcerts%2Fca.cert"
		kmipEndpoint     = "csfle-kmip-" + PETNAME + ".mdbtraining.net"
		encryptedClient  *mongo.Client
		client           *mongo.Client
		exitCode         = 0
		result           *mongo.InsertOneResult
		dekFindResult    bson.M
		dek              primitive.Binary
		kmipTLSConfig    *tls.Config
		err							 error
	)

	defer func() {
		os.Exit(exitCode)
	}()

	provider := "kmip"
	kmsProvider := map[string]map[string]interface{}{
		provider: {
			"endpoint": kmipEndpoint,
		},
	}

	client, err = createClient(connectionString)
	if err != nil {
		fmt.Printf("MDB client error: %s\n", err)
		exitCode = 1
		return
	}

	coll := client.Database("__encryption").Collection("__keyVault")

	// Set the KMIP TLS options
	kmsTLSOptions := make(map[string]*tls.Config)
	tlsOptions := map[string]interface{}{
		"tlsCAFile": "/etc/pki/tls/certs/ca.cert",
		"tlsCertificateKeyFile": "/home/ec2-user/server.pem",
	}
	kmipTLSConfig, err = options.BuildTLSConfig(tlsOptions)
	if err != nil {
		fmt.Printf("Cannot create KMS TLS Config: %s\n", err)
		exitCode = 1
		return
	}
	kmsTLSOptions["kmip"] = kmipTLSConfig

	firstname, lastname := nameGenerator()
	payload := bson.M{
		"name": bson.M{
			"firstName": firstname,
			"lastName": lastname,
			"otherNames": nil,
		},
		"address": bson.M{
			"streetAddress": "29 Bson Street",
			"suburbCounty": "Mongoville",
			"stateProvince": "Victoria",
			"zipPostcode": "3999",
			"country": "Oz",
		},
		"dob": time.Date(1999, 1, 12, 0, 0, 0, 0, time.Local),
		"phoneNumber": "1800MONGO",
		"salary": 999999.99,
		"taxIdentifier": "78SDSSWN001",
		"role": []string{"Student"},
	}

	// Retrieve our DEK
	opts := options.FindOne().SetProjection(bson.D{{Key: "_id", Value: 1}})
	err = coll.FindOne(context.TODO(), bson.D{{Key: "keyAltNames", Value: "dataKey1"}}, opts).Decode(&dekFindResult)
	if err != nil || len(dekFindResult) == 0 {
		fmt.Printf("DEK find error: %s\n", err)
		exitCode = 1
		return
	}
	dek = dekFindResult["_id"].(primitive.Binary)


	db := "companyData"
	collection := "employee"

	schemaMap := bson.M{
		db + "." + collection: bson.M{
			"bsonType": "object",
			"encryptMetadata": bson.M{
				"keyId": bson.A{
					dek,
				},
				"algorithm": "AEAD_AES_256_CBC_HMAC_SHA_512-Random",
			},
			"properties": bson.M{
				"name": bson.M{
					"bsonType": "object",
					"properties": bson.M{
						"firstname": bson.M{
							"encrypt": bson.M{
								"bsonType":  "string",
								"algorithm": "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic",
							},
						},
						// PUT MORE FIELDS IN HERE
					},
		// PUT THE REST OF YOUR SCHEMA MAP CODE HERE
	}

	// Auto Encryption Client
	encryptedClient, err = createAutoEncryptionClient(connectionString, keySpace, kmsProvider, kmsTLSOptions, schemaMap)
	if err != nil {
		fmt.Printf("MDB encrypted client error: %s\n", err)
		exitCode = 1
		return
	}

	encryptedColl := encryptedClient.Database(db).Collection(collection)

	// remove the otherNames field if it is nil
	name := payload["name"].(bson.M)
	if name["otherNames"] == nil {
		fmt.Println("Removing nil")
		delete(name, "otherNames")
	}

	result, err = encryptedColl.InsertOne(context.TODO(), payload)
	if err != nil {
		fmt.Printf("Insert error: %s\n", err)
		exitCode = 1
		return
	}
	fmt.Print(result.InsertedID)

	exitCode = 0
}
	