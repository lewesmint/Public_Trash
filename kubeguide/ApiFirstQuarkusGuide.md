
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

All Quarkus commands in this guide use Maven plugins (e.g., `mvn io.quarkus.platform:quarkus-maven-plugin:3.28.4:create` or `./mvnw quarkus:dev`), which download and run Quarkus automatically. You never need to install Quarkus separately.

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
mvn io.quarkus.platform:quarkus-maven-plugin:3.28.4:create -DprojectGroupId=com.example -DprojectArtifactId=my-app
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

You have two options for creating the parent project:

- **Option A (Maven Archetype)**: Uses the standard Maven approach for creating parent POMs. It's cleaner (no unwanted files generated) but requires a couple of extra manual steps to add the Quarkus BOM and Maven wrapper.

- **Option B (Quarkus Plugin)**: Uses the Quarkus tooling which is faster and automatically includes the Quarkus BOM and Maven wrapper, but it generates example source code that you'll need to delete since a parent project shouldn't contain any application code.

**Choose one option and follow all its steps:**

---

### Option A: Using Maven Archetype (Recommended - Clean, No Cleanup Needed)

This approach uses the standard Maven POM archetype designed specifically for parent projects. It creates only a `pom.xml` file with no source code.

#### Step 1: Create the parent project

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

#### Step 2: Add the Quarkus BOM

Open `pom.xml` and add this inside the `<project>` tag:

```xml
<properties>
  <quarkus.platform.version>3.28.4</quarkus.platform.version>
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

#### Step 3: Verify packaging is set to `pom`

Ensure your `pom.xml` has `<packaging>pom</packaging>` after the `<version>` tag:

```xml
<project ...>
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example.nevada</groupId>
  <artifactId>my-new-service-parent</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>pom</packaging>
  ...
```

This should already be set correctly by the archetype.

At this point, your directory should look like this:

```
my-new-service-parent/
└── pom.xml
```

#### Step 4: Add the Maven wrapper

The archetype doesn't create a Maven wrapper, so add it now:

```bash
mvn wrapper:wrapper -Dmaven=3.9.6
```

This creates the `mvnw`, `mvnw.cmd`, and `.mvn/wrapper/` files.

#### Step 5: Verify the final structure

> **Tip:** Use `tree -a` to show hidden directories (those starting with `.`) and their contents:
> ```bash
> tree -a
> ```

After adding the wrapper, your parent directory should now look like this:

```
my-new-service-parent/
├── pom.xml
├── mvnw
├── mvnw.cmd
└── .mvn/
    └── wrapper/
        └── maven-wrapper.properties
```

> **Note:** The newer Maven wrapper plugin (3.3.4+) no longer generates `maven-wrapper.jar` in the `.mvn/wrapper/` directory by default. Instead, it downloads the JAR on first use. This is normal and the wrapper will work correctly.

**No `src/` directory should exist.**

**Done!** Proceed to Step 2.

---

### Option B: Using Quarkus Plugin (Simpler but Requires Cleanup)

This approach is faster but generates unwanted source files that you'll need to delete.

#### Step 1: Create the parent project

```bash
mvn -N io.quarkus.platform:quarkus-maven-plugin:3.28.4:create \
  -DprojectGroupId=com.example.nevada \
  -DprojectArtifactId=my-new-service-parent \
  -DplatformVersion=3.28.4 \
  -Dextensions=""

cd my-new-service-parent
```

> **Note:** Despite the `-N` flag and empty extensions, this command will generate a `src/` directory with example code because the Quarkus plugin is designed to create runnable applications.

#### Step 2: Delete unwanted source files

Check for unwanted files:

```bash
ls -la src/ 2>/dev/null && echo "WARNING: src/ directory exists in parent!" || echo "Good: No src/ directory"
```

If the `src/` directory exists, delete it:

```bash
rm -rf src/
```

> **Note:** You may see `.mvn/wrapper/MavenWrapperDownloader.java` when searching for Java files—that's fine! It's part of the Maven wrapper infrastructure, not application code. We're only concerned with the `src/` directory.

#### Step 3: Verify packaging is set to `pom`

Open the parent `pom.xml` and ensure it contains `<packaging>pom</packaging>` after the `<version>` tag:

```xml
<project ...>
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example.nevada</groupId>
  <artifactId>my-new-service-parent</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>pom</packaging>
  ...
```

This should already be set correctly by the Quarkus plugin.

#### Step 4: Verify the structure

Your parent directory should now look like this:

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

**No `src/` directory should exist.**

**Done!** Proceed to Step 2.

---

---

## 2. Create the API Module

> **Before you run the next command:**
> Make sure you are in your parent project directory (e.g., `cd my-new-service-parent`).

> **Note:** This guide uses the **standalone OpenAPI Generator Maven plugin** rather than the Quarkus OpenAPI Generator extension. The standalone plugin gives you full control over package names and code generation options, which the Quarkus extension doesn't support.

### Step 1: Create the API Module

```bash
./mvnw io.quarkus.platform:quarkus-maven-plugin:3.28.4:create \
  -DprojectGroupId=com.example.nevada.api \
  -DprojectArtifactId=my-new-service-api \
  -DplatformVersion=3.28.4 \
  -DnoCode
```

**What this does:**
- Creates a new module directory `my-new-service-api/` with its own `pom.xml`
- **Automatically adds the module to the parent `pom.xml`** in a `<modules>` section
- The `-DnoCode` option tells Quarkus **not to generate any default resource or example code** - you only want code generated from your OpenAPI spec

After running this, your parent `pom.xml` will be updated to include:

```xml
<modules>
  <module>my-new-service-api</module>
</modules>
```

This tells Maven that `my-new-service-api` is part of the multi-module build.

### Step 2: Fix the API Module POM

**IMPORTANT:** The `quarkus:create` command generates a module with its own `<dependencyManagement>` section and `quarkus.platform.*` properties. This is redundant since the module inherits from the parent POM, and it's a Maven best practice to manage versions only in the parent.

Open `my-new-service-api/pom.xml` and **remove** the entire `<dependencyManagement>` section and the `quarkus.platform.*` properties:

**Remove these lines:**
```xml
<properties>
    ...
    <quarkus.platform.artifact-id>quarkus-bom</quarkus.platform.artifact-id>
    <quarkus.platform.group-id>io.quarkus.platform</quarkus.platform.group-id>
    <quarkus.platform.version>3.28.4</quarkus.platform.version>  <!-- REMOVE THIS! -->
    ...
</properties>

<dependencyManagement>  <!-- REMOVE THIS ENTIRE SECTION! -->
    <dependencies>
        <dependency>
            <groupId>${quarkus.platform.group-id}</groupId>
            <artifactId>${quarkus.platform.artifact-id}</artifactId>
            <version>${quarkus.platform.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

The module will inherit the Quarkus version from the parent's `<dependencyManagement>` section instead, keeping version management centralized.

### Step 3: Create the OpenAPI Specification

Create the OpenAPI spec file:

```bash
# From the parent directory (my-new-service-parent):
cd my-new-service-api
mkdir -p src/main/openapi
```

Now create the file `src/main/openapi/my-new-service.yaml`:

> **Tip:** From the `my-new-service-api` directory, you can create the empty file and all necessary parent directories in one command using:
> ```bash
> install -D /dev/null src/main/openapi/my-new-service.yaml
> ```
> This creates an empty file and any missing parent directories.

**Important:** Open `src/main/openapi/my-new-service.yaml` in your editor and paste in the following OpenAPI specification:

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

### Step 4: Add Required Dependencies and Configure Code Generation

The Quarkus OpenAPI Generator extension has a known limitation where it doesn't respect package configuration. Instead, we'll use the **standalone OpenAPI Generator Maven plugin** which gives full control over package names and code generation.

**Edit `my-new-service-api/pom.xml`** and add the following dependencies in the `<dependencies>` section:

```xml
<dependencies>
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-arc</artifactId>
    </dependency>
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-rest-client-jackson</artifactId>
    </dependency>
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-rest</artifactId>
    </dependency>
    <dependency>
        <groupId>jakarta.validation</groupId>
        <artifactId>jakarta.validation-api</artifactId>
    </dependency>
    <dependency>
        <groupId>io.smallrye</groupId>
        <artifactId>smallrye-open-api-core</artifactId>
    </dependency>
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-junit5</artifactId>
        <scope>test</scope>
    </dependency>
</dependencies>
```

**What these dependencies provide:**
- `quarkus-arc` - CDI dependency injection
- `quarkus-rest-client-jackson` - JSON serialisation/deserialisation
- `quarkus-rest` - JAX-RS REST endpoints support
- `jakarta.validation-api` - Bean validation annotations
- `smallrye-open-api-core` - MicroProfile OpenAPI annotations used by generated code

Now add the **OpenAPI Generator Maven plugin** in the `<build><plugins>` section, **before** the `quarkus-maven-plugin`:

```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.openapitools</groupId>
            <artifactId>openapi-generator-maven-plugin</artifactId>
            <version>7.5.0</version>
            <executions>
                <execution>
                    <id>generate-server</id>
                    <goals>
                        <goal>generate</goal>
                    </goals>
                    <configuration>
                        <inputSpec>${project.basedir}/src/main/openapi/my-new-service.yaml</inputSpec>
                        <generatorName>jaxrs-spec</generatorName>
                        <configOptions>
                            <apiPackage>com.example.nevada.api</apiPackage>
                            <modelPackage>com.example.nevada.api.model</modelPackage>
                            <library>quarkus</library>
                            <dateLibrary>java8</dateLibrary>
                            <generateBuilders>true</generateBuilders>
                            <openApiNullable>false</openApiNullable>
                            <useBeanValidation>true</useBeanValidation>
                            <generatePom>false</generatePom>
                            <interfaceOnly>true</interfaceOnly>
                            <returnResponse>true</returnResponse>
                            <sourceFolder>.</sourceFolder>
                            <useJakartaEe>true</useJakartaEe>
                            <useMicroProfileOpenAPIAnnotations>true</useMicroProfileOpenAPIAnnotations>
                            <useSwaggerAnnotations>false</useSwaggerAnnotations>
                        </configOptions>
                        <output>${project.build.directory}/generated-sources/openapi</output>
                    </configuration>
                </execution>
            </executions>
        </plugin>
        <plugin>
            <groupId>io.quarkus.platform</groupId>
            <artifactId>quarkus-maven-plugin</artifactId>
            <version>${quarkus.platform.version}</version>
            <!-- rest of quarkus-maven-plugin configuration -->
        </plugin>
        <!-- other plugins -->
    </plugins>
</build>
```

**Key configuration options:**
- `apiPackage` - Package for generated API interfaces (e.g., `com.example.nevada.api`)
- `modelPackage` - Package for generated model classes (e.g., `com.example.nevada.api.model`)
- `library: quarkus` - Generates Quarkus-compatible code
- `interfaceOnly: true` - Only generates interfaces, not implementations
- `useMicroProfileOpenAPIAnnotations: true` - Adds MicroProfile OpenAPI annotations
- `useJakartaEe: true` - Uses Jakarta EE packages (required for Quarkus 3.x)

### Step 5: Generate API Code from the OpenAPI Spec

Now that you have the OpenAPI spec and plugin configuration in place, generate the Java interfaces and model classes.

> **Note:** JAVA_HOME must be set to your JDK installation path for this step to work. If JAVA_HOME is not set, code generation may fail even if previous Maven or Quarkus commands worked. See [Troubleshooting: JAVA_HOME](#5-troubleshooting) below for help.

> **Before running the next command:**
> Make sure you're in the parent project directory. If you're still in the `my-new-service-api` directory from the previous step, navigate back:
> ```bash
> cd ..
> ```

**From the `my-new-service-parent` directory, run:**

```bash
./mvnw -pl my-new-service-api clean compile
```

**What this does:**
- `-pl my-new-service-api` tells Maven to run the command only in the API module
- `clean` removes any previous build outputs
- `compile` triggers the OpenAPI Generator plugin (during the generate-sources phase) and then compiles the generated code
- Uses the parent Maven wrapper to ensure consistent Maven version

### Step 6: Verify the Generated Code

**IMPORTANT:** The generated code is placed in `my-new-service-api/target/generated-sources/openapi/`, **NOT** in `src/main/java/`.

- The `target/` directory is where Maven puts all build outputs (compiled classes, generated sources, etc.)
- **Do NOT manually edit files in `target/`** - they are regenerated every time you run the build
- The generated code is automatically included in the compilation classpath
- You will **implement** these generated interfaces in your service module's `src/main/java/` directory (in Step 3)

Check the generated files:

```bash
# From: my-new-service-parent/
tree my-new-service-api/target/generated-sources/openapi/ -I 'src|.openapi-generator|.dockerignore|README.md'
```

**Expected package structure:**
```
my-new-service-api/target/generated-sources/openapi/
└── com
    └── example
        └── nevada
            ├── RestApplication.java
            ├── RestResourceRoot.java
            └── api
                ├── HelloApi.java
                └── model
                    └── HelloResponse.java
```

**This is the correct structure** - the code is generated in your configured packages (`com.example.nevada.api` and `com.example.nevada.api.model`).

When you implement your service in Step 3, you'll import from these packages:
```java
import com.example.nevada.api.HelloApi;
import com.example.nevada.api.model.HelloResponse;
```

---

## 3. Create the Service Module

```bash
./mvnw io.quarkus.platform:quarkus-maven-plugin:3.28.4:create \
  -DprojectGroupId=com.example.nevada.svc \
  -DprojectArtifactId=my-new-service \
  -DplatformVersion=3.28.4 \
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

### Clean Up the Service Module POM

Just like the API module, the service module also has redundant `<dependencyManagement>` and `quarkus.platform.*` properties that should be removed.

Open `my-new-service/pom.xml` and **remove** the entire `<dependencyManagement>` section and the `quarkus.platform.*` properties:

**Remove these lines:**
```xml
<properties>
    ...
    <quarkus.platform.artifact-id>quarkus-bom</quarkus.platform.artifact-id>
    <quarkus.platform.group-id>io.quarkus.platform</quarkus.platform.group-id>
    <quarkus.platform.version>3.28.4</quarkus.platform.version>  <!-- REMOVE THIS! -->
    ...
</properties>

<dependencyManagement>  <!-- REMOVE THIS ENTIRE SECTION! -->
    <dependencies>
        <dependency>
            <groupId>${quarkus.platform.group-id}</groupId>
            <artifactId>${quarkus.platform.artifact-id}</artifactId>
            <version>${quarkus.platform.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

The module will inherit the Quarkus version from the parent's `<dependencyManagement>` section.

- Add Quarkus REST and JSON extensions:

For Quarkus 3.x, use the following extension names (the older `quarkus-resteasy-reactive` and `quarkus-resteasy-reactive-jackson` are no longer used):

```bash
# From the parent directory (my-new-service-parent):
cd my-new-service
../mvnw quarkus:add-extension -Dextensions="quarkus-rest,quarkus-rest-jackson,quarkus-smallrye-openapi"
cd ..
```

This will add REST, JSON, and OpenAPI support to your service module. The `quarkus-smallrye-openapi` extension enables the `/q/openapi` and `/q/swagger-ui` endpoints for testing your API.

- Implement the generated interfaces (from the API module) in your service code under `src/main/java`.

**Example Implementation:**

Create `my-new-service/src/main/java/com/example/nevada/svc/GreetingResource.java`:

```java
package com.example.nevada.svc;

import com.example.nevada.api.HelloApi;
import com.example.nevada.api.model.HelloResponse;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.core.Response;

@Path("/hello")
@ApplicationScoped
public class GreetingResource implements HelloApi {

    @Override
    public Response hello() {
        HelloResponse response = new HelloResponse();
        response.setMessage("Hello from My New Service!");
        return Response.ok(response).build();
    }
}
```

> **Important:** You must add the `@Path("/hello")` annotation to the implementation class, even though the interface already has it. This is required for JAX-RS to properly register the resource endpoint.

> **Note on naming:** The implementation class is named `GreetingResource`, but it implements `HelloApi` (which was generated from the `Greeting` tag in the OpenAPI spec). The implementation class name doesn't need to match the interface name or tag name - you can name it whatever makes sense for your service. What matters is that it implements the generated API interface.

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

## 5. Verifying API Contract Enforcement

One of the key benefits of API-first development is that the service implementation is **forced** to follow the API contract. Let's verify this is working.

### How We Know the Service Follows the API

#### 1. Compile-Time Contract Enforcement

The service class **implements the generated API interface**:

```java
@Path("/hello")
@ApplicationScoped
public class GreetingResource implements HelloApi {
    @Override
    public Response hello() {
        HelloResponse response = new HelloResponse();
        response.setMessage("Hello from My New Service!");
        return Response.ok(response).build();
    }
}
```

**Key points:**
- If the method signature doesn't match the interface, the code won't compile
- If you forget to implement a method, the code won't compile
- If you change the return type, the code won't compile

#### 2. The API Interface Defines the Contract

The generated `HelloApi` interface (in `my-new-service-api/target/generated-sources/openapi/com/example/nevada/api/HelloApi.java`):

```java
@Path("/hello")
public interface HelloApi {
    @GET
    @Produces({ "application/json" })
    @org.eclipse.microprofile.openapi.annotations.Operation(operationId = "hello", ...)
    Response hello();
}
```

This interface was generated from your OpenAPI spec and defines:
- The HTTP method (`@GET`)
- The path (`@Path("/hello")`)
- The response type (`Response`)
- The content type (`@Produces({ "application/json" })`)

#### 3. Runtime Verification

Test the endpoint:

```bash
curl http://localhost:8080/hello
```

Expected response:
```json
{"message":"Hello from My New Service!"}
```

This matches the `HelloResponse` schema defined in your OpenAPI spec.

#### 4. What Happens If You Break the Contract?

The compiler will catch violations. Here are examples that **won't compile**:

**Example 1: Wrong return type**
```java
public String hello() {  // ❌ Won't compile - must return Response
    return "Hello";
}
// Error: The return type is incompatible with HelloApi.hello()
```

**Example 2: Wrong method signature**
```java
public Response hello(String name) {  // ❌ Won't compile - interface has no parameters
    ...
}
// Error: The method hello(String) of type GreetingResource must override or implement a supertype method
```

**Example 3: Missing implementation**
```java
public class GreetingResource implements HelloApi {
    // ❌ Won't compile - must implement hello()
}
// Error: The type GreetingResource must implement the inherited abstract method HelloApi.hello()
```

#### 5. Key Benefits

✅ **Type safety**: Compiler enforces the contract
✅ **No drift**: Service can't deviate from the API spec
✅ **Refactoring safety**: If you change the OpenAPI spec and regenerate, any breaking changes will cause compile errors
✅ **Documentation accuracy**: The OpenAPI spec is always the source of truth

This is the **core value of API-first development** - the contract is enforced at compile time, not just documented!

---

## 6. Adding a New Endpoint (API-First Workflow)

Let's add a new endpoint to demonstrate the full API-first workflow and see how the contract enforcement works.

> **Prerequisites for this section:**
> - Make sure you're in the parent project directory (`my-new-service-parent`)
> - **If you still have `quarkus:dev` running from Section 4, stop it now** by pressing `Ctrl+C` in the terminal where it's running
> - We need to stop it to avoid port conflicts and to clearly demonstrate the compilation error in the next steps

### Step 1: Update the OpenAPI Specification

Edit `my-new-service-api/src/main/openapi/my-new-service.yaml` and add a new operation to the existing `/hello` path:

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

    post:
      operationId: greetPerson
      tags:
        - Greeting
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/GreetingRequest'
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GreetingResponse'

components:
  schemas:
    HelloResponse:
      type: object
      properties:
        message:
          type: string

    GreetingRequest:
      type: object
      required:
        - name
      properties:
        name:
          type: string

    GreetingResponse:
      type: object
      properties:
        greeting:
          type: string
        timestamp:
          type: string
          format: date-time
```

> **Important:** We're adding a **POST** operation to the same `/hello` path. This will add a new method to the existing `HelloApi` interface, which will cause a compilation error in `HelloResource` until we implement it.

### Step 2: Regenerate the API Code

From the parent directory:

```bash
./mvnw -pl my-new-service-api clean compile
```

This will regenerate the `HelloApi` interface with the new `greetPerson` method.

### Step 3: Install the Updated API Module

**IMPORTANT:** Before we can see the compilation error in the service module, we need to install the updated API module into the local Maven repository. Otherwise, the service module will continue using the old version of the API.

```bash
./mvnw -pl my-new-service-api install
```

This ensures the service module will pick up the new `HelloApi` interface with the `greetPerson` method.

### Step 4: Observe the Compilation Error

Now try to build the service module with a clean build to see the compilation error:

```bash
./mvnw -pl my-new-service clean compile
```

> **Note:** We use `clean compile` here to force a rebuild. Without `clean`, Maven might report "Nothing to compile - all classes are up to date" because it doesn't detect that the API interface has changed.

**You'll see a compilation error:**

```
[ERROR] /path/to/my-new-service/src/main/java/com/example/nevada/svc/GreetingResource.java:[11,8]
GreetingResource is not abstract and does not override abstract method greetPerson(GreetingRequest) in HelloApi
```

This is **exactly what we want!** The compiler is enforcing the API contract. The `HelloApi` interface now has a new method `greetPerson(GreetingRequest)` that `GreetingResource` must implement.

**This demonstrates the power of API-first development:** You cannot deploy code that doesn't match the API contract - the compiler prevents it!

### Step 5: Implement the New Endpoint

Update `my-new-service/src/main/java/com/example/nevada/svc/GreetingResource.java` to implement the new method:

```java
package com.example.nevada.svc;

import com.example.nevada.api.HelloApi;
import com.example.nevada.api.model.GreetingRequest;
import com.example.nevada.api.model.GreetingResponse;
import com.example.nevada.api.model.HelloResponse;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.core.Response;
import java.time.OffsetDateTime;

@Path("/hello")
@ApplicationScoped
public class GreetingResource implements HelloApi {

    @Override
    public Response hello() {
        HelloResponse response = new HelloResponse();
        response.setMessage("Hello from My New Service!");
        return Response.ok(response).build();
    }

    @Override
    public Response greetPerson(GreetingRequest greetingRequest) {
        GreetingResponse response = new GreetingResponse();
        response.setGreeting("Hello, " + greetingRequest.getName() + "!");
        response.setTimestamp(OffsetDateTime.now());
        return Response.ok(response).build();
    }
}
```

> **Note:** The OpenAPI Generator creates one API interface per path. Since we added a POST operation to the existing `/hello` path, it added the `greetPerson` method to the existing `HelloApi` interface. Our `GreetingResource` class must implement both methods.

### Step 6: Build and Test

Build the service:

```bash
./mvnw -pl my-new-service compile
```

**Now it compiles successfully!** ✅

Run the service in dev mode:

```bash
cd my-new-service
../mvnw quarkus:dev
```

Test both endpoints:

```bash
# Test the GET endpoint
curl http://localhost:8080/hello

# Expected response:
# {"message":"Hello from My New Service!"}

# Test the new POST endpoint
curl -X POST http://localhost:8080/hello \
  -H "Content-Type: application/json" \
  -d '{"name":"World"}'

# Expected response:
# {"greeting":"Hello, World!","timestamp":"2025-10-18T02:10:30.123Z"}
```

### Step 7: What We Learned

This workflow demonstrates:

1. **API-first approach**: We defined the API contract in the OpenAPI spec first
2. **Code generation**: The API interface was automatically generated with the new method
3. **Compile-time enforcement**: The service wouldn't compile until we implemented the new method
4. **Type safety**: The generated `GreetingResponse` class ensures we return the correct structure
5. **No drift**: It's impossible for the service to deviate from the API contract

**This is the power of API-first development with code generation!**

---

## 7. Troubleshooting

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

## 8. Best Practices for OpenAPI Specs

To get clean, well-named generated code:

1. **Always use `tags`** to organise operations and control API interface names:
   ```yaml
   paths:
     /hello:
       get:
         tags: [Greeting]  # Generates HelloApi.java (from the tag name)
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

## 9. Summary

- The API module holds the OpenAPI spec and generated code.
- The service module implements the API.
- You can update the spec, regenerate code, and keep API and implementation cleanly separated.
- Use the standalone OpenAPI Generator Maven plugin for full control over package names and code generation options.
- Generated code appears in `target/generated-sources/openapi/` in your configured packages (e.g., `com.example.nevada.api`).

This is a true API-first, multi-module Quarkus setup.

---

> **Note:** When you run the `mvn ...:create` command to generate a new module, you may see other modules (like `my-new-service-api`) marked as "SKIPPED" in the output. This is normal—only the new module is created or affected by this command. All modules will be built together when you run a full build (e.g., `./mvnw install`).
