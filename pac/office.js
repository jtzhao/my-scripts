var proxy = "PROXY 147.2.207.100:3128"
var direct = "DIRECT";

var domains_via_proxy = [
    "*.suse.com",
    "*.novell.com",
    "*nytimes.com",
];

var ips_via_proxy = [
    ["10.0.0.0", "255.0.0.0"],
    ["147.2.0.0", "255.255.0.0"],
];


function FindProxyForURL(url, host) {
    for (var i in domains_via_proxy) {
        if (shExpMatch(host, domains_via_proxy[i])) {
            return proxy;
        }
    }
    for (var i in ips_via_proxy) {
        if (isInNet(host, ips_via_proxy[i][0], ips_via_proxy[i][1])) {
            return proxy;
        }
    }
    return direct;
}
