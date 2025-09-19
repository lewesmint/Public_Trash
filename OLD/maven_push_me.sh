# 1) Show the exact goals Maven would execute (no build)
mvn fr.jcgay.maven.plugins:buildplan-maven-plugin:list -DskipTests

# 2) See the merged POM Maven actually uses
mvn -q help:effective-pom > effective-pom.xml

# 3) Search for known image plugins and push/build goals
grep -nE "(jib-maven-plugin|dockerfile-maven-plugin|docker-maven-plugin|exec-maven-plugin)" effective-pom.xml
grep -nE "<phase>(package|install|deploy)</phase>" -n effective-pom.xml
grep -nE "(jib:build|dockerfile:push|docker:push)" effective-pom.xml
