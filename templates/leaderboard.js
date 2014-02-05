var data = [
{% for user in handles %}
  ["{{user}}" {% for score in scores[user] %} , "{{ '%0.2f' % (score)}}" {% endfor %} ],
{% endfor %}
];
