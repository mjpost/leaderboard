var data = [
{% for user in handles %}
  ["{{user}}" {% for score in scores[user] %} , "{{ '%0.3f' % (score)}}" {% endfor %} ],
{% endfor %}
];

var hidden_users = {
{% for user in hidden_users %}
  "{{ user }}": 1,
{% endfor %}
};

var names = {
{% for handle in names.keys() %}
  "{{ handle }}": "{{ names[handle] }}",
{% endfor %}
};
