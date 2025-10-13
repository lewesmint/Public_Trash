
# API-First Quarkus Service: Step-by-Step Guide

This guide walks you through a true API-first workflow for Quarkus:

1. **Create a parent project** (multi-module Maven setup)
2. **Create an API module** (for your OpenAPI spec and generated code)
3. **Add your OpenAPI spec** to the API module
4. **Configure and run code generation** in the API module
5. **Create a service module** (for your implementation)
6. **Add a dependency on the API module** in the service module
7. **Implement the generated interfaces** in the service module
8. **Build and run your service**

This ensures your implementation always matches your API contract, and you can evolve your API independently of your service logic.

---

# Prerequisites: Check Maven and Java Versions

Before starting, ensure you are using a supported Maven and Java version. Quarkus 3.x requires Maven 3.8.1+ and Java 17+ (Java 21 recommended).

- To check the version used by the Maven Wrapper (`./mvnw`):
  ```bash
  ./mvnw --version
  ```
- To check your system Maven version:
  ```bash
  mvn --version
  ```

> **Tip:** The Maven Wrapper (`./mvnw`) ensures a consistent Maven version for your project, regardless of your system Maven. Prefer using `./mvnw` for all project commands unless otherwise specified.

---

## 1. Create a Parent Project


```bash
mvn -N io.quarkus.platform:quarkus-maven-plugin:3.10.0:create \
  -DprojectGroupId=com.example.nevada \
  -DprojectArtifactId=my-new-service-parent \
  -DplatformVersion=3.10.0 \
  -Dextensions=""
cd my-new-service-parent
```

> **About `-N` (or `--non-recursive`):**
> The `-N` flag tells Maven to only run the command in the current directory (the parent project), and not to build or create any submodules. This ensures you get a parent POM project (a container for your modules), not a runnable Quarkus application. This is exactly what you want for a multi-module setup.

---

## Important: Set Parent Packaging to pom

After running the parent project creation command in Step 1, you must ensure the parent `pom.xml` contains the following line after the `<version>` tag:

```xml
<packaging>pom</packaging>
```

If it is missing, add it manually. This is required for multi-module Maven projects and for Step 2 to work.

Your parent `pom.xml` should look like this at the top:

```xml
<project ...>
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example.nevada</groupId>
  <artifactId>my-new-service-parent</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>pom</packaging>
  ...
```

Now proceed to Step 2.

---

## 2. Create the API Module

> **Before you run the next command:**
> Make sure you are in your parent project directory (e.g., `cd my-new-service-parent`).


```bash
mvn io.quarkus.platform:quarkus-maven-plugin:3.10.0:create \
  -DprojectGroupId=com.example.nevada.api \
  -DprojectArtifactId=my-new-service-api \
  -DnoCode
```

> **Note:** The `-DnoCode` option tells Quarkus **not to generate any default resource or example code** in the new module. This is important for API-first development, where you want the code to be generated only from your OpenAPI spec, not from Quarkus templates.

- In `my-new-service-api`, create `src/main/openapi/my-new-service.yaml` with your OpenAPI spec. See example below:

> **Tip:** To create the OpenAPI YAML file and all necessary parent directories in one line, use:
> ```bash
> install -D /dev/null src/main/openapi/my-new-service.yaml
> ```

```yaml
openapi: 3.0.3
info:
  title: My New Service API
  version: 0.1.0
paths:
  /hello:

    get:
      operationId: hello
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  message:
                    type: string
```

- Add the Quarkus OpenAPI Generator extension to the API module:

```bash
cd my-new-service-api
../mvnw quarkus:add-extension -Dextensions="quarkus-openapi-generator,quarkus-rest-client-jackson"
cd ..
```

This ensures all required dependencies are present for code generation.

- In `my-new-service-api/src/main/resources/application.properties`, configure code generation:

```
quarkus.openapi-generator.codegen.input-spec=my-new-service.yaml
quarkus.openapi-generator.codegen.base-package=com.example.nevada.api.mynewservice
quarkus.openapi-generator.codegen.return-response=true
```

> **Note:** If you are using a different Quarkus or plugin version, check the [Quarkus OpenAPI Generator documentation](https://quarkus.io/guides/openapi-generator) for the latest configuration options.

- Run code generation:

> **Note:** JAVA_HOME must be set to your JDK installation path for this step to work. If JAVA_HOME is not set, code generation may fail even if previous Maven or Quarkus commands worked. See [Troubleshooting: JAVA_HOME](#5-troubleshooting) below for help.

**Run this command from the `my-new-service-parent` directory:**

```bash
./mvnw -pl my-new-service-api quarkus:generate-code
```

This ensures code is generated in the correct module using the parent Maven wrapper.

- Generated sources will appear in `target/generated-sources/openapi`.

---

## 3. Create the Service Module

```bash
mvn io.quarkus.platform:quarkus-maven-plugin:3.10.0:create \
  -DprojectGroupId=com.example.nevada.svc \
  -DprojectArtifactId=my-new-service \
  -DnoCode
```

- Add a dependency on the API module in `my-new-service/pom.xml`:

This allows your service implementation to use the interfaces and DTOs generated from your OpenAPI spec, ensuring your service always matches the API contract defined in the API module.

```xml
<dependency>
  <groupId>com.example.nevada.api</groupId>
  <artifactId>my-new-service-api</artifactId>
  <version>${project.version}</version>
</dependency>
```

- Add Quarkus REST and JSON extensions:

For Quarkus 3.x, use the following extension names (the older `quarkus-resteasy-reactive` and `quarkus-resteasy-reactive-jackson` are no longer used):

```bash
cd my-new-service
../mvnw quarkus:add-extension -Dextensions="quarkus-rest,quarkus-rest-jackson"
cd ..
```

This will add REST and JSON support to your service module.

- Implement the generated interfaces (from the API module) in your service code under `src/main/java`.

---

## 4. Build and Run

- Build all modules:
```bash
./mvnw install
```
- Run the service module in dev mode:
```bash
cd my-new-service
../mvnw quarkus:dev
```
- Visit:
  - http://localhost:8080/hello
  - http://localhost:8080/q/openapi

---

## 5. Troubleshooting:

### 1. Set JAVA_HOME


You must set the JAVA_HOME environment variable to your JDK installation path. For example, if you are using Bash and your JDK is installed at `/usr/lib/jvm/java-21-openjdk-amd64`, run:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH
```

To find your current JDK location, you can run:
```bash
readlink -f $(which java) | sed 's:/bin/java::'
```

> **To make JAVA_HOME persistent:**
> - Append the following lines to your `~/.bashrc` file (this will auto-detect your Java installation):
>   ```bash
>   echo "export JAVA_HOME=$(readlink -f $(which java) | sed 's:/bin/java::')" >> ~/.bashrc
>   echo 'export PATH=$JAVA_HOME/bin:$PATH' >> ~/.bashrc
>   ```
> - Then run `source ~/.bashrc` or restart your terminal to apply the changes.

### 2. Add Required Dependencies

If you see an error about missing `quarkus-rest-client-jackson`, add this to your `my-new-service-api/pom.xml`:

```xml
<dependency>
  <groupId>io.quarkus</groupId>
  <artifactId>quarkus-rest-client-jackson</artifactId>
</dependency>
```

Then re-run the code generation command from the parent directory.

### 3. Using JBang! or JDK Version Managers

If you use JBang!, SDKMAN!, jEnv, or another tool to manage/switch JDKs:

- Make sure the correct JDK version (e.g., Java 21+) is active before running Maven or Quarkus commands.
- You can check your current Java version with:
  ```bash
  java -version
  ```
- For JBang!:
  - Use `jbang jdk --help` to see how to set the JDK for your session or globally.
  - Example to set Java 21 for your shell:
    ```bash
    jbang jdk use 21
    ```
- For SDKMAN!:
  - List installed JDKs: `sdk list java`
  - Set JDK for current shell: `sdk use java <version>`
  - Set default JDK: `sdk default java <version>`
- For jEnv:
  - Set JDK for current shell: `jenv shell <version>`
  - Set global JDK: `jenv global <version>`

After switching, confirm with `java -version` and ensure JAVA_HOME is set (most managers do this automatically). Then proceed with the build steps.

---

### Why did earlier builds work without JAVA_HOME?

Some systems set JAVA_HOME automatically, or tools may find Java on your PATH. However, for reliable builds, always set JAVA_HOME explicitly as described above.

---

## 6. Summary

- The API module holds the OpenAPI spec and generated code.
- The service module implements the API.
- You can update the spec, regenerate code, and keep API and implementation cleanly separated.

This is a true API-first, multi-module Quarkus setup.

---

> **Note:** When you run the `mvn ...:create` command to generate a new module, you may see other modules (like `my-new-service-api`) marked as "SKIPPED" in the output. This is normal—only the new module is created or affected by this command. All modules will be built together when you run a full build (e.g., `./mvnw install`).
