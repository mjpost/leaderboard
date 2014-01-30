var data = [
{% for user in handles %}
  ["{{user}}" {% for score in scores[user] %} , "{{score}}" {% endfor %} ],
{% endfor %}
];
