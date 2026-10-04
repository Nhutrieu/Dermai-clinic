FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY services services
RUN mvn -q -DskipTests package
FROM eclipse-temurin:21-jre
ARG SERVICE
WORKDIR /app
RUN useradd -r -u 10001 dermai
COPY --from=build /src/services/${SERVICE}/target/*.jar app.jar
USER dermai
ENTRYPOINT ["java","-XX:InitialRAMPercentage=10","-XX:MaxRAMPercentage=65","-XX:+UseSerialGC","-jar","app.jar"]
