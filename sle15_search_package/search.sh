#!/bin/bash
function search_repo()
{
    local repo="$1"
    local arch="$2"
    local pattern="$3"
    for suffix in $arch noarch; do
        local url="$repo/$arch/DVD1/$suffix/"
        local output=$(curl -s "$url" | grep -oP '(?<=")[^"]+\.rpm(?=")' | sort -h | uniq | grep -i "$pattern")
        if [[ -n "$output" ]]; then
            echo "[$url]"
            echo -e "$output\n"
        fi
    done
}

function usage()
{
    echo "Usage: $0 URL PRODUCT PACKAGE [VERSION] [ARCH]" 1>&2
}

if [[ $# -lt 3 ]]; then
    usage
    exit 255
fi

URL="$1"
PRODUCT="$2"
PACKAGE="$3"
VERSION="$4"
[[ -z "$VERSION" ]] && VERSION="LATEST"
ARCH="$5"
[[ -z "$ARCH" ]] && ARCH="x86_64"

# Check Leanos
search_repo "$URL/$PRODUCT-Leanos-$VERSION" $ARCH $PACKAGE
# Check Modules
MODULES=$(curl -s "$URL/" | grep -oP "$PRODUCT-Module-[\w\-]+-$VERSION" | sort -h | uniq)
for module in $MODULES; do
    search_repo "$URL/$module" $ARCH $PACKAGE
done
