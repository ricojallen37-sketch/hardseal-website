(function(){
  var keys = ["src", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];
  var params = new URLSearchParams(window.location.search);
  var values = {};
  keys.forEach(function(key){
    var value = params.get(key);
    if(value) values[key] = value.slice(0, 160);
  });
  if(!values.src && !values.utm_source && !values.utm_campaign) return;

  function encodeQuery(query){
    var parts = [];
    query.forEach(function(value, key){
      parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(value));
    });
    return parts.join("&");
  }

  function sourceText(){
    var lines = [];
    if(values.src) lines.push("Source tag: " + values.src);
    if(values.utm_source) lines.push("UTM source: " + values.utm_source);
    if(values.utm_medium) lines.push("UTM medium: " + values.utm_medium);
    if(values.utm_campaign) lines.push("UTM campaign: " + values.utm_campaign);
    if(values.utm_content) lines.push("UTM content: " + values.utm_content);
    if(values.utm_term) lines.push("UTM term: " + values.utm_term);
    return lines.join("\n");
  }

  function decorateMailto(anchor){
    var href = anchor.getAttribute("href");
    var parts = href.split("?");
    var address = parts[0];
    var query = new URLSearchParams(parts.slice(1).join("?"));
    var marker = "Source tag:";
    var body = query.get("body") || "";
    if(body.indexOf(marker) === -1){
      body = body ? body + "\n\n" + sourceText() : sourceText();
      query.set("body", body);
    }
    if(!query.has("subject")) query.set("subject", "Hardseal inquiry");
    anchor.setAttribute("href", address + "?" + encodeQuery(query));
  }

  function decorateInternal(anchor){
    var href = anchor.getAttribute("href");
    if(!href || href.charAt(0) === "#" || /^javascript:/i.test(href) || /^tel:/i.test(href)) return;
    if(/^mailto:/i.test(href)){
      decorateMailto(anchor);
      return;
    }
    var url;
    try{
      url = new URL(href, window.location.href);
    }catch(err){
      return;
    }
    if(url.origin !== window.location.origin) return;
    keys.forEach(function(key){
      if(values[key] && !url.searchParams.has(key)) url.searchParams.set(key, values[key]);
    });
    anchor.setAttribute("href", url.pathname + url.search + url.hash);
  }

  document.addEventListener("DOMContentLoaded", function(){
    Array.prototype.forEach.call(document.querySelectorAll("a[href]"), decorateInternal);
  });
})();
