# Make a temp folder and fetch installer
TMPDIR=$(mktemp -d)
curl -Ls https://sh.jbang.dev -o "$TMPDIR/jbang-install.sh"
chmod +x "$TMPDIR/jbang-install.sh"

# Initial setup (adds ~/.jbang/bin to PATH via your shell rc)
"$TMPDIR/jbang-install.sh" app setup

# Trust Quarkus CLI artifacts + install CLI
"$TMPDIR/jbang-install.sh" trust add https://repo1.maven.org/maven2/io/quarkus/quarkus-cli/
"$TMPDIR/jbang-install.sh" app install --fresh --force quarkus@quarkusio

# Install JDK 21 and set it default for JBang
"$TMPDIR/jbang-install.sh" jdk install 21
"$TMPDIR/jbang-install.sh" jdk default 21

# Clean up
rm -rf "$TMPDIR"
