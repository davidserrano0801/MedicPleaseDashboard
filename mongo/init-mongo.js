const databaseName = process.env.MONGO_DATABASE || "plataforma";
const appUser = process.env.MONGO_APP_USER;
const appPassword = process.env.MONGO_APP_PASSWORD;

if (!appUser || !appPassword) {
  throw new Error("Faltan MONGO_APP_USER o MONGO_APP_PASSWORD");
}

const appDb = db.getSiblingDB(databaseName);
const existing = appDb.getUser(appUser);

if (!existing) {
  appDb.createUser({
    user: appUser,
    pwd: appPassword,
    roles: [{ role: "readWrite", db: databaseName }]
  });
  print(`Usuario de aplicación creado en ${databaseName}`);
} else {
  print(`El usuario ${appUser} ya existe`);
}
