
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

# Prerequisites: Java and Maven Setup

Before starting, ensure you are using a supported Maven and Java version. Quarkus 3.x requires Maven 3.8.1+ and Java 17+ (Java 21 recommended).

## Check Your Java Version

```bash
java -version
```

You should see Java 17 or higher (Java 21 recommended).

## Set JAVA_HOME (Required)

**JAVA_HOME must be set** for Maven builds and code generation to work properly. Even if `java` is on your PATH, many Maven plugins require JAVA_HOME.

**To find your Java installation:**
```bash
readlink -f $(which java) | sed 's:/bin/java::'
```

**Set JAVA_HOME for your current session:**
```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64  # Use your actual path
export PATH=$JAVA_HOME/bin:$PATH
```

**Make JAVA_HOME persistent (recommended):**

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
# Auto-detect and set JAVA_HOME
export JAVA_HOME=$(readlink -f $(which java) | sed 's:/bin/java::')
export PATH=$JAVA_HOME/bin:$PATH
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

**Verify JAVA_HOME is set:**
```bash
echo $JAVA_HOME
# Should output something like: /usr/lib/jvm/java-21-openjdk-amd64
```

### Using JDK Version Managers

If you use **SDKMAN!**, **jEnv**, **JBang!**, or similar tools:

- **SDKMAN!**:
  ```bash
  sdk list java                    # List available JDKs
  sdk install java 21-tem          # Install Java 21 (Temurin)
  sdk use java 21-tem              # Use for current shell
  sdk default java 21-tem          # Set as default
  ```
  SDKMAN! automatically sets JAVA_HOME.

- **jEnv**:
  ```bash
  jenv versions                    # List installed JDKs
  jenv global 21                   # Set global version
  jenv shell 21                    # Set for current shell
  ```
  Enable the export plugin: `jenv enable-plugin export` (sets JAVA_HOME automatically)

- **JBang!**:
  ```bash
  jbang jdk list                   # List available JDKs
  jbang jdk install 21             # Install Java 21
  jbang jdk use 21                 # Use for current shell
  ```

After switching JDK versions, always verify:
```bash
java -version
echo $JAVA_HOME
```

## Do You Need to Install Quarkus CLI?

**Short answer: No, you don't need to install the Quarkus CLI for this guide.**

All Quarkus commands in this guide use Maven plugins (e.g., `mvn io.quarkus.platform:quarkus-maven-plugin:3.10.0:create` or `./mvnw quarkus:dev`), which download and run Quarkus automatically. You never need to install Quarkus separately.

### When You MIGHT Want the Quarkus CLI

The Quarkus CLI provides shorter, more convenient commands:

**With Quarkus CLI installed:**
```bash
quarkus create app com.example:my-app
quarkus dev
quarkus add extension rest
```

**Without Quarkus CLI (Maven-based, what this guide uses):**
```bash
mvn io.quarkus.platform:quarkus-maven-plugin:3.10.0:create -DprojectGroupId=com.example -DprojectArtifactId=my-app
./mvnw quarkus:dev
./mvnw quarkus:add-extension -Dextensions=rest
```

**Install Quarkus CLI if you want:**
- Shorter, more memorable commands
- To work with Quarkus projects frequently
- Interactive project creation with prompts

**Don't install Quarkus CLI if you:**
- Prefer explicit Maven commands (better for CI/CD scripts)
- Want everything version-controlled in your `pom.xml`
- Are following this guide exactly as written

**To install Quarkus CLI (optional):**
```bash
# Using SDKMAN! (recommended)
sdk install quarkus

# Using Homebrew (macOS/Linux)
brew install quarkusio/tap/quarkus

# Using JBang!
jbang app install --fresh --force quarkus@quarkusio
```

> **Bottom line:** This guide works perfectly without installing Quarkus CLI. The Maven-based approach is more explicit and works everywhere Maven works.

## Check Maven Version

- To check the version used by the Maven Wrapper (`./mvnw`):
  ```bash
  ./mvnw --version
  ```
- To check your system Maven version:
  ```bash
  mvn --version
  ```

> **Tip:** The Maven Wrapper (`./mvnw`) ensures a consistent Maven version for your project, regardless of your system Maven. Prefer using `./mvnw` for all project commands unless otherwise specified.

### Installing or Updating the Maven Wrapper

If you don't have a Maven Wrapper in your project, or want to update it to a specific version, use the Maven Wrapper Plugin:

**To install/update to the latest Maven version:**
```bash
mvn wrapper:wrapper
```

**To install/update to a specific Maven version:**
```bash
mvn wrapper:wrapper -Dmaven=3.9.6
```

**If you don't have Maven installed at all**, you can download the wrapper directly:
```bash
# Download the wrapper JAR
curl -o .mvn/wrapper/maven-wrapper.jar https://repo.maven.apache.org/maven2/org/apache/maven/wrapper/maven-wrapper/3.2.0/maven-wrapper-3.2.0.jar

# Download the wrapper script for Linux/Mac
curl -o mvnw https://raw.githubusercontent.com/apache/maven-wrapper/master/mvnw
chmod +x mvnw

# Download the wrapper script for Windows
curl -o mvnw.cmd https://raw.githubusercontent.com/apache/maven-wrapper/master/mvnw.cmd
```

Then edit `.mvn/wrapper/maven-wrapper.properties` to set your desired Maven version:
```properties
distributionUrl=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.6/apache-maven-3.9.6-bin.zip
```

> **Note:** The Quarkus project creation commands automatically generate a Maven Wrapper for you, so you typically don't need to do this manually unless you want to change the Maven version.

### Running Maven in Docker

If you prefer not to install Maven or Java locally, you can run all Maven commands using Docker:

**Using the official Maven Docker image:**
```bash
docker run -it --rm \
  -v "$PWD":/usr/src/project \
  -v "$HOME/.m2":/root/.m2 \
  -w /usr/src/project \
  maven:3.9.6-eclipse-temurin-21 \
  mvn clean install
```

**Create an alias for convenience:**
```bash
# Add to your ~/.bashrc or ~/.zshrc
alias mvn-docker='docker run -it --rm -v "$PWD":/usr/src/project -v "$HOME/.m2":/root/.m2 -w /usr/src/project maven:3.9.6-eclipse-temurin-21 mvn'

# Then use it like regular Maven:
mvn-docker clean install
mvn-docker quarkus:dev
```

**For Quarkus dev mode with port mapping:**
```bash
docker run -it --rm \
  -v "$PWD":/usr/src/project \
  -v "$HOME/.m2":/root/.m2 \
  -w /usr/src/project \
  -p 8080:8080 \
  -p 5005:5005 \
  maven:3.9.6-eclipse-temurin-21 \
  mvn quarkus:dev -Dquarkus.http.host=0.0.0.0
```

> **Important Notes:**
> - The `-v "$HOME/.m2":/root/.m2` mount caches Maven dependencies between runs
> - Port 8080 is for the application, 5005 is for remote debugging
> - Use `-Dquarkus.http.host=0.0.0.0` to make Quarkus listen on all interfaces (required for Docker)
> - You can change the Maven/Java version by using different image tags (e.g., `maven:3.9.6-eclipse-temurin-17`)

**Available Maven Docker image tags:**
- `maven:3.9.6-eclipse-temurin-21` - Maven 3.9.6 with Java 21 (recommended for Quarkus 3.x)
- `maven:3.9.6-eclipse-temurin-17` - Maven 3.9.6 with Java 17
- `maven:3.8.8-eclipse-temurin-21` - Maven 3.8.8 with Java 21
- See all tags at: https://hub.docker.com/_/maven

---

## 1. Create a Parent Project

The parent project is a container that will hold your API and service modules. It's not a runnable application itself—it just coordinates the build of all your modules and manages shared dependencies and versions.

**What this command does:**
- Creates a Maven project with `<packaging>pom</packaging>` (a parent/aggregator project)
- Creates only a `pom.xml` file with no source directories
- Uses the standard Maven POM archetype (designed specifically for parent projects)

### Option A: Using Maven Archetype (Recommended - No cleanup needed)

This creates a clean parent POM with no source files:

```bash
mvn archetype:generate \
  -DarchetypeGroupId=org.codehaus.mojo.archetypes \
  -DarchetypeArtifactId=pom-root \
  -DarchetypeVersion=RELEASE \
  -DgroupId=com.example.nevada \
  -DartifactId=my-new-service-parent \
  -Dversion=1.0.0-SNAPSHOT \
  -DinteractiveMode=false

cd my-new-service-parent
```

Then add the Quarkus BOM to the generated `pom.xml`. Open `pom.xml` and add this inside the `<project>` tag:

```xml
<properties>
  <quarkus.platform.version>3.10.0</quarkus.platform.version>
  <maven.compiler.source>21</maven.compiler.source>
  <maven.compiler.target>21</maven.compiler.target>
  <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
</properties>

<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>io.quarkus.platform</groupId>
      <artifactId>quarkus-bom</artifactId>
      <version>${quarkus.platform.version}</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

### Option B: Using Quarkus Plugin (Requires cleanup)

This is simpler but generates unwanted source files that you'll need to delete:

```bash
mvn -N io.quarkus.platform:quarkus-maven-plugin:3.10.0:create \
  -DprojectGroupId=com.example.nevada \
  -DprojectArtifactId=my-new-service-parent \
  -DplatformVersion=3.10.0 \
  -Dextensions=""
cd my-new-service-parent
```

> **Note:** Despite the `-N` flag and empty extensions, this command may still generate a `src/` directory with example code. You'll need to delete it in the next step.

---

## Important: Verify the Parent Project

After creating the parent project, verify its structure.

### 1. Check for Unwanted Source Files (Option B only)

**If you used Option A (Maven archetype):** Skip this step—no cleanup needed!

**If you used Option B (Quarkus plugin):** The parent may have generated unwanted source files.

**Check what was created:**
```bash
ls -la src/ 2>/dev/null && echo "WARNING: src/ directory exists in parent!" || echo "Good: No src/ directory"
```

**If the `src/` directory exists, DELETE it:**
```bash
# Remove the entire src directory if it exists
rm -rf src/
```

> **Note:** You may see `.mvn/wrapper/MavenWrapperDownloader.java` when searching for Java files—that's fine! It's part of the Maven wrapper infrastructure, not application code. We're only concerned with the `src/` directory.

The parent is just a container—it should have no application source code.

### 2. Verify Parent Packaging is Set to `pom`

Open the parent `pom.xml` and ensure it contains the following line after the `<version>` tag:

```xml
<packaging>pom</packaging>
```

**If you used Option A (Maven archetype):** This is already set correctly.

**If you used Option B (Quarkus plugin):** Verify it's present. If missing, add it manually.

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

### 3. Verify the Parent Structure

**If you used Option A (Maven archetype):**
```
my-new-service-parent/
└── pom.xml
```

**If you used Option B (Quarkus plugin):**
```
my-new-service-parent/
├── pom.xml
├── mvnw
├── mvnw.cmd
└── .mvn/
    └── wrapper/
        ├── maven-wrapper.jar
        └── maven-wrapper.properties
```

**In both cases: No `src/` directory should exist in the parent.**

### 4. Add Maven Wrapper (Option A only)

If you used Option A, you don't have a Maven wrapper yet. Add it now:

```bash
mvn wrapper:wrapper -Dmaven=3.9.6
```

This creates the `mvnw`, `mvnw.cmd`, and `.mvn/wrapper/` files.

> **Why Option B generates source files:**
> Despite using `-N` and `extensions=""`, the Quarkus Maven plugin is designed to create runnable applications, so it generates example code. Option A uses the standard Maven POM archetype which is specifically designed for parent projects, so it doesn't generate any source code.

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
servers:
  - url: http://localhost:8080
    description: Development server
paths:
  /hello:
    get:
      operationId: hello
      tags:
        - Greeting
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HelloResponse'

components:
  schemas:
    HelloResponse:
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

```properties
# Spec-specific configuration (required for Quarkus 3.x)
quarkus.openapi-generator.codegen.spec.my_new_service_yaml.base-package=com.example.nevada.api.mynewservice
quarkus.openapi-generator.codegen.spec.my_new_service_yaml.additional-api-type-annotations=@jakarta.ws.rs.Path("/")
```

> **Important Configuration Notes:**
> - The configuration format changed in newer Quarkus versions. Use `spec.<spec-file-name-with-underscores>.<property>` format.
> - The spec file name in the configuration uses underscores: `my_new_service_yaml` (not `my-new-service.yaml`).
> - The `additional-api-type-annotations` adds the `@Path` annotation to the generated API interface, which is required for JAX-RS.
> - If you are using a different Quarkus or plugin version, check the [Quarkus OpenAPI Generator documentation](https://quarkus.io/guides/openapi-generator) for the latest configuration options.

- Run code generation:

> **Note:** JAVA_HOME must be set to your JDK installation path for this step to work. If JAVA_HOME is not set, code generation may fail even if previous Maven or Quarkus commands worked. See [Troubleshooting: JAVA_HOME](#5-troubleshooting) below for help.

**Run this command from the `my-new-service-parent` directory:**

```bash
./mvnw -pl my-new-service-api quarkus:generate-code
```

This ensures code is generated in the correct module using the parent Maven wrapper.

- Generated sources will appear in `target/generated-sources/open-api`.

> **What Gets Generated:**
> Based on the example OpenAPI spec above, you should see:
> - `com/example/nevada/api/mynewservice/api/GreetingApi.java` - The API interface (from the `tags` field)
> - `com/example/nevada/api/mynewservice/model/HelloResponse.java` - The response model (from the schema name)
>
> If you see `DefaultApi.java` or `Hello200Response.java` instead, the configuration didn't apply correctly. Check that:
> 1. The property names match exactly (including `my_new_service_yaml` with underscores)
> 2. The `application.properties` file is in `src/main/resources/`
> 3. You're using the spec-specific configuration format shown above

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

**Example Implementation:**

Create `my-new-service/src/main/java/com/example/nevada/svc/GreetingResource.java`:

```java
package com.example.nevada.svc;

import com.example.nevada.api.mynewservice.api.GreetingApi;
import com.example.nevada.api.mynewservice.model.HelloResponse;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.core.Response;

@ApplicationScoped
public class GreetingResource implements GreetingApi {

    @Override
    public Response hello() {
        HelloResponse response = new HelloResponse();
        response.setMessage("Hello from My New Service!");
        return Response.ok(response).build();
    }
}
```

> **Note:** The class name and package can be whatever you want. What matters is that it implements the generated API interface (`GreetingApi` in this example).

---

## 4. Build and Run

Build all modules from the parent directory:
```bash
./mvnw clean install
```

> **Important:** You must run `./mvnw install` (or `./mvnw clean install`) from the parent directory before running the service in dev mode. This installs the API module into your local Maven repository so the service module can find it.

- Run the service module in dev mode:
```bash
cd my-new-service
../mvnw quarkus:dev
```

- Test your service:
  - API endpoint: http://localhost:8080/hello
  - OpenAPI spec: http://localhost:8080/q/openapi
  - Swagger UI: http://localhost:8080/q/swagger-ui

> **Expected Response from /hello:**
> ```json
> {
>   "message": "Hello from My New Service!"
> }
> ```

---

## 5. Troubleshooting:

### 1. JAVA_HOME Not Set

**Problem:** Code generation fails with errors about missing Java or JAVA_HOME.

**Solution:** Make sure JAVA_HOME is set. See the [Prerequisites: Set JAVA_HOME](#set-java_home-required) section above for detailed instructions.

**Quick check:**
```bash
echo $JAVA_HOME
# Should output your JDK path, not empty
```

### 2. Code Generation Issues

**Problem: Generated code is in wrong package (e.g., `org.openapi.quarkus.my_new_service_yaml` instead of your base-package)**

**Solution:** Make sure you're using the spec-specific configuration format in `application.properties`:

```properties
quarkus.openapi-generator.codegen.spec.my_new_service_yaml.base-package=com.example.nevada.api.mynewservice
```

Note: The spec name uses underscores (`my_new_service_yaml`), not the original filename.

**Problem: Generated interface is called `DefaultApi` instead of a meaningful name**

**Solution:** Add `tags` to your OpenAPI operations. The tag name becomes the API interface name (e.g., `tags: [Greeting]` generates `GreetingApi.java`).

**Problem: Missing `quarkus-rest-client-jackson` dependency**

**Solution:** This should have been added by the `quarkus:add-extension` command. If you see errors, manually add to `my-new-service-api/pom.xml`:

```xml
<dependency>
  <groupId>io.quarkus</groupId>
  <artifactId>quarkus-rest-client-jackson</artifactId>
</dependency>
```

Then re-run the code generation command from the parent directory.

### 3. Build Failures After Switching JDK Versions

**Problem:** Builds fail after switching Java versions with SDKMAN!, jEnv, or JBang!

**Solution:**
1. Verify the correct JDK is active: `java -version`
2. Verify JAVA_HOME is set correctly: `echo $JAVA_HOME`
3. If using jEnv, enable the export plugin: `jenv enable-plugin export`
4. See the [Using JDK Version Managers](#using-jdk-version-managers) section in Prerequisites for detailed setup.

### 4. Module Not Found Errors

**Problem:** Service module can't find classes from the API module.

**Solution:** You must run `./mvnw install` from the parent directory to install the API module into your local Maven repository before the service module can use it.

```bash
# From the parent directory
./mvnw clean install
```

---

## 6. Best Practices for OpenAPI Specs

To get clean, well-named generated code:

1. **Always use `tags`** to organise operations and control API interface names:
   ```yaml
   paths:
     /hello:
       get:
         tags: [Greeting]  # Generates GreetingApi.java
   ```

2. **Define schemas in `components/schemas`** instead of inline:
   ```yaml
   components:
     schemas:
       HelloResponse:  # Generates HelloResponse.java
         type: object
         properties:
           message:
             type: string
   ```

3. **Define servers** to avoid warnings:
   ```yaml
   servers:
     - url: http://localhost:8080
       description: Development server
   ```

4. **Use meaningful `operationId`** values - these become method names in the generated interface.

---

## 7. Workflow: Updating Your API

When you need to change your API:

1. **Update the OpenAPI spec** in `my-new-service-api/src/main/openapi/my-new-service.yaml`

2. **Regenerate the code** (from parent directory):
   ```bash
   ./mvnw -pl my-new-service-api clean quarkus:generate-code
   ```

3. **Rebuild the API module**:
   ```bash
   ./mvnw -pl my-new-service-api install
   ```

4. **Update your implementation** in the service module to match the new interface

5. **Test the changes**:
   ```bash
   cd my-new-service
   ../mvnw quarkus:dev
   ```

> **Tip:** If you add new operations or change method signatures, your IDE will show compilation errors in the service module until you update the implementation. This is the API-first contract enforcement in action!

---

## 8. Summary

- The API module holds the OpenAPI spec and generated code.
- The service module implements the API.
- You can update the spec, regenerate code, and keep API and implementation cleanly separated.
- Always use spec-specific configuration format: `quarkus.openapi-generator.codegen.spec.<spec-name>.<property>`

This is a true API-first, multi-module Quarkus setup.

---

> **Note:** When you run the `mvn ...:create` command to generate a new module, you may see other modules (like `my-new-service-api`) marked as "SKIPPED" in the output. This is normal—only the new module is created or affected by this command. All modules will be built together when you run a full build (e.g., `./mvnw install`).
