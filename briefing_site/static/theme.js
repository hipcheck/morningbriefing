(function(){
  var key = 'briefing_theme';
  function setTheme(t){
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem(key, t); } catch(e) {}
  }
  function getPreferred(){
    try {
      var v = localStorage.getItem(key);
      if (v === 'dark' || v === 'light') return v;
    } catch(e) {}
    return 'dark';
  }

  document.addEventListener('DOMContentLoaded', function(){
    setTheme(getPreferred());
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', function(){
      var cur = document.documentElement.getAttribute('data-theme') || 'dark';
      setTheme(cur === 'dark' ? 'light' : 'dark');
    });
  });
})();
